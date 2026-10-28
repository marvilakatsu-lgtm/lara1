import os
import sqlite3
from datetime import datetime, timezone

import aiosqlite
from levels import nivel_por_xp

CURRENT_SCHEMA_VERSION = 2

SCHEMA = """
CREATE TABLE IF NOT EXISTS schema_migrations (
    version    INTEGER PRIMARY KEY,
    name       TEXT NOT NULL,
    applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS users (
    user_id   INTEGER PRIMARY KEY,
    xp        INTEGER NOT NULL DEFAULT 0,
    denarios  INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS platinas (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL,
    game        TEXT NOT NULL,
    platform    TEXT NOT NULL,
    earned_at   TEXT NOT NULL,
    proof_url   TEXT NOT NULL,
    proof_msg_id INTEGER,
    status      TEXT NOT NULL DEFAULT 'pending',   -- pending | approved | rejected
    reviewer_id INTEGER,
    created_at  TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_plat_user ON platinas(user_id, status);

-- Sistema de runs Soulslike integrado
CREATE TABLE IF NOT EXISTS sl_games (
    id   INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE COLLATE NOCASE
);
CREATE TABLE IF NOT EXISTS sl_challenges (
    id    INTEGER PRIMARY KEY AUTOINCREMENT,
    name  TEXT NOT NULL UNIQUE COLLATE NOCASE,
    rules TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS sl_runs (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id       INTEGER NOT NULL,
    game_id       INTEGER NOT NULL,
    challenge_id  INTEGER NOT NULL,
    build         TEXT NOT NULL DEFAULT '',
    seconds       INTEGER NOT NULL,
    proof_msg_id  INTEGER,
    proof_url     TEXT NOT NULL DEFAULT '',
    status        TEXT NOT NULL DEFAULT 'pending',
    reviewer_id   INTEGER,
    reject_reason TEXT,
    created_at    TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_sl_cat ON sl_runs(game_id, challenge_id, status);
CREATE TABLE IF NOT EXISTS platina_proofs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    platina_id INTEGER NOT NULL,
    proof_url TEXT NOT NULL,
    media_type TEXT,
    FOREIGN KEY(platina_id) REFERENCES platinas(id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS zerados (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id          INTEGER NOT NULL,
    game             TEXT NOT NULL,
    platform         TEXT NOT NULL,
    finished_at      TEXT NOT NULL,
    comment          TEXT NOT NULL DEFAULT '',
    xp_awarded       INTEGER NOT NULL DEFAULT 0,
    denarios_awarded INTEGER NOT NULL DEFAULT 0,
    created_at       TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_zer_user ON zerados(user_id);
CREATE TABLE IF NOT EXISTS kv (
    key   TEXT PRIMARY KEY,
    value TEXT
);
CREATE TABLE IF NOT EXISTS perfis (
    user_id     INTEGER PRIMARY KEY,
    thread_id   INTEGER NOT NULL,
    card_msg_id INTEGER,
    tagline     TEXT NOT NULL DEFAULT '',
    bio         TEXT NOT NULL DEFAULT '',
    fav_game    TEXT NOT NULL DEFAULT '',
    theme       TEXT NOT NULL DEFAULT 'Ouro',
    links       TEXT NOT NULL DEFAULT '{}'
);
CREATE TABLE IF NOT EXISTS inventario (
    user_id     INTEGER NOT NULL,
    item        TEXT NOT NULL,
    tipo        TEXT NOT NULL,
    equipado    INTEGER NOT NULL DEFAULT 0,
    comprado_em TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id, item)
);
CREATE TABLE IF NOT EXISTS logs (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    actor_id   INTEGER NOT NULL,
    action     TEXT NOT NULL,
    details    TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Configuração por servidor e trilha de auditoria administrativa.
CREATE TABLE IF NOT EXISTS guild_settings (
    guild_id   INTEGER NOT NULL,
    key        TEXT NOT NULL,
    value      TEXT NOT NULL,
    updated_by INTEGER,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (guild_id, key)
);
CREATE TABLE IF NOT EXISTS module_settings (
    guild_id   INTEGER NOT NULL,
    module_key TEXT NOT NULL,
    enabled    INTEGER NOT NULL DEFAULT 1 CHECK (enabled IN (0, 1)),
    updated_by INTEGER,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (guild_id, module_key)
);
CREATE TABLE IF NOT EXISTS admin_audit (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id   INTEGER NOT NULL,
    actor_id   INTEGER NOT NULL,
    action     TEXT NOT NULL,
    entity     TEXT NOT NULL DEFAULT '',
    before_val TEXT,
    after_val  TEXT,
    result     TEXT NOT NULL DEFAULT 'success',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_admin_audit_guild_time ON admin_audit(guild_id, created_at DESC);

-- Sistema de clãs: os registros são preservados mesmo se os canais forem excluídos.
CREATE TABLE IF NOT EXISTS clans (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id           INTEGER NOT NULL,
    name               TEXT NOT NULL,
    tag                TEXT NOT NULL,
    slug               TEXT NOT NULL,
    description        TEXT NOT NULL DEFAULT '',
    main_game          TEXT NOT NULL,
    play_style         TEXT NOT NULL,
    creator_id         INTEGER NOT NULL,
    leader_id          INTEGER NOT NULL,
    status             TEXT NOT NULL DEFAULT 'provisioning',
    recruitment        TEXT NOT NULL DEFAULT 'applications',
    category_id        INTEGER,
    chat_channel_id    INTEGER,
    announcements_id   INTEGER,
    strategies_id      INTEGER,
    voice_channel_id   INTEGER,
    created_at         TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at         TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    closed_at          TEXT,
    UNIQUE (guild_id, slug),
    UNIQUE (guild_id, creator_id)
);
CREATE INDEX IF NOT EXISTS idx_clans_guild_status ON clans(guild_id, status);
CREATE TABLE IF NOT EXISTS clan_members (
    guild_id  INTEGER NOT NULL,
    clan_id   INTEGER NOT NULL REFERENCES clans(id) ON DELETE RESTRICT,
    user_id   INTEGER NOT NULL,
    role      TEXT NOT NULL DEFAULT 'member' CHECK (role IN ('leader', 'officer', 'member')),
    joined_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (guild_id, user_id)
);
CREATE INDEX IF NOT EXISTS idx_clan_members_clan ON clan_members(guild_id, clan_id);
CREATE TABLE IF NOT EXISTS clan_members_history (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id   INTEGER NOT NULL,
    clan_id    INTEGER NOT NULL REFERENCES clans(id) ON DELETE RESTRICT,
    user_id    INTEGER NOT NULL,
    role       TEXT NOT NULL,
    joined_at  TEXT NOT NULL,
    left_at    TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    exit_reason TEXT NOT NULL DEFAULT 'left'
);
CREATE INDEX IF NOT EXISTS idx_clan_members_history_guild ON clan_members_history(guild_id, clan_id, user_id);
CREATE TABLE IF NOT EXISTS clan_invites (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id    INTEGER NOT NULL,
    clan_id     INTEGER NOT NULL REFERENCES clans(id) ON DELETE RESTRICT,
    inviter_id  INTEGER NOT NULL,
    invitee_id  INTEGER NOT NULL,
    status      TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'accepted', 'rejected', 'expired', 'revoked')),
    expires_at  TEXT NOT NULL,
    created_at  TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_clan_invites_target ON clan_invites(guild_id, invitee_id, status);
CREATE UNIQUE INDEX IF NOT EXISTS idx_clan_invites_one_pending ON clan_invites(guild_id, clan_id, invitee_id) WHERE status='pending';
CREATE TABLE IF NOT EXISTS clan_applications (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id    INTEGER NOT NULL,
    clan_id     INTEGER NOT NULL REFERENCES clans(id) ON DELETE RESTRICT,
    user_id     INTEGER NOT NULL,
    message     TEXT NOT NULL DEFAULT '',
    status      TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'accepted', 'rejected', 'withdrawn')),
    decided_by  INTEGER,
    created_at  TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    decided_at  TEXT
);
CREATE INDEX IF NOT EXISTS idx_clan_apps_target ON clan_applications(guild_id, clan_id, status);
CREATE UNIQUE INDEX IF NOT EXISTS idx_clan_apps_one_pending ON clan_applications(guild_id, clan_id, user_id) WHERE status='pending';
CREATE TABLE IF NOT EXISTS clan_activities (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id    INTEGER NOT NULL,
    clan_id     INTEGER NOT NULL REFERENCES clans(id) ON DELETE RESTRICT,
    creator_id  INTEGER NOT NULL,
    title       TEXT NOT NULL,
    activity_type TEXT NOT NULL,
    scheduled_at TEXT,
    status      TEXT NOT NULL DEFAULT 'planned' CHECK (status IN ('planned', 'completed', 'cancelled')),
    created_at  TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_clan_activities_guild ON clan_activities(guild_id, clan_id, status);

-- Rejeita atomicamente o 11º membro, mesmo em operações concorrentes.
CREATE TRIGGER IF NOT EXISTS trg_clan_member_limit
BEFORE INSERT ON clan_members
WHEN (SELECT COUNT(*) FROM clan_members WHERE guild_id = NEW.guild_id AND clan_id = NEW.clan_id) >= 10
BEGIN
    SELECT RAISE(ABORT, 'clan_member_limit');
END;
"""


class Database:
    def __init__(self, path: str):
        self.path = path
        self.conn: aiosqlite.Connection | None = None

    def _backup_existing_database_before_upgrade(self) -> str | None:
        """Cria snapshot SQLite antes de alterar um banco sem a versão atual do schema."""
        if not os.path.isfile(self.path) or os.path.getsize(self.path) == 0:
            return None
        try:
            probe = sqlite3.connect(self.path, timeout=10)
            try:
                exists = probe.execute(
                    "SELECT 1 FROM sqlite_master WHERE type='table' AND name='schema_migrations'"
                ).fetchone()
                version = 0
                if exists:
                    row = probe.execute("SELECT MAX(version) FROM schema_migrations").fetchone()
                    version = int(row[0] or 0)
            finally:
                probe.close()
        except sqlite3.Error:
            # Banco existente inválido: não tente corrigir por cima de um arquivo não verificável.
            raise RuntimeError(f"Não foi possível verificar o schema do banco existente: {self.path}")
        if version >= CURRENT_SCHEMA_VERSION:
            return None
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        backup_path = f"{self.path}.pre-migration-{stamp}.bak"
        try:
            source = sqlite3.connect(self.path, timeout=10)
            target = sqlite3.connect(backup_path)
            try:
                source.backup(target)
            finally:
                target.close()
                source.close()
        except Exception as exc:
            try:
                if os.path.exists(backup_path):
                    os.remove(backup_path)
            except OSError:
                pass
            raise RuntimeError(f"Falhou o backup automático antes da migração: {exc}") from exc
        return backup_path

    async def connect(self):
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        backup_path = self._backup_existing_database_before_upgrade()
        if backup_path:
            print(f"[database] Snapshot pré-migração criado: {backup_path}")
        self.conn = await aiosqlite.connect(self.path)
        self.conn.row_factory = aiosqlite.Row
        await self.conn.execute("PRAGMA foreign_keys=ON")
        await self.conn.executescript(SCHEMA)

        applied = await self._one("SELECT MAX(version) AS version FROM schema_migrations")
        version = int(applied["version"] or 0) if applied else 0
        if version < 1:
            # Migração versionada 1: bancos antigos não tinham o ID da mensagem de comprovante.
            cols = [r["name"] for r in await self._all("PRAGMA table_info(platinas)")]
            if "proof_msg_id" not in cols:
                await self.conn.execute("ALTER TABLE platinas ADD COLUMN proof_msg_id INTEGER")
            await self.conn.execute(
                "INSERT INTO schema_migrations(version,name) VALUES(1,?)",
                ("platinas_proof_message_id",),
            )
            version = 1
        if version < 2:
            # O SCHEMA acima cria aditivamente configurações/admin/clãs; esta linha registra o marco.
            await self.conn.execute(
                "INSERT INTO schema_migrations(version,name) VALUES(2,?)",
                ("central_settings_admin_audit_and_clans",),
            )
        await self.conn.commit()

    async def _one(self, sql, args=()):
        async with self.conn.execute(sql, args) as cur:
            return await cur.fetchone()

    async def _all(self, sql, args=()):
        async with self.conn.execute(sql, args) as cur:
            return await cur.fetchall()

    async def log(self, actor_id: int, action: str, details: str = ""):
        await self.conn.execute(
            "INSERT INTO logs(actor_id, action, details) VALUES (?,?,?)",
            (actor_id, action, details),
        )
        await self.conn.commit()

    # ---------- usuários ----------
    async def get_user(self, user_id: int):
        await self.conn.execute("INSERT OR IGNORE INTO users(user_id) VALUES (?)", (user_id,))
        await self.conn.commit()
        return await self._one("SELECT * FROM users WHERE user_id=?", (user_id,))

    async def add_reward(self, user_id: int, xp: int, denarios: int):
        """Soma XP/Denários e devolve (nível_antigo, nível_novo, xp_total)."""
        user = await self.get_user(user_id)
        antigo = nivel_por_xp(user["xp"])
        # MAX(0, ...) evita saldo negativo quando uma recompensa é devolvida (ex.: /remover_zerado).
        await self.conn.execute(
            "UPDATE users SET xp = MAX(0, xp + ?), denarios = MAX(0, denarios + ?) WHERE user_id=?",
            (xp, denarios, user_id),
        )
        await self.conn.commit()
        novo_xp = max(0, user["xp"] + xp)
        return antigo, nivel_por_xp(novo_xp), novo_xp

    async def posicao_xp(self, xp: int) -> int:
        row = await self._one("SELECT COUNT(*)+1 AS p FROM users WHERE xp > ?", (xp,))
        return row["p"]

    # ---------- platinas ----------
    async def platina_duplicada(self, user_id: int, game: str, platform: str) -> bool:
        row = await self._one(
            """SELECT 1 FROM platinas WHERE user_id=? AND lower(game)=lower(?)
               AND lower(platform)=lower(?) AND status IN ('pending','approved')""",
            (user_id, game, platform),
        )
        return row is not None

    async def criar_platina(self, user_id, game, platform, earned_at, proof_url, proof_msg_id=None) -> int:
        cur = await self.conn.execute(
            "INSERT INTO platinas(user_id, game, platform, earned_at, proof_url, proof_msg_id) VALUES (?,?,?,?,?,?)",
            (user_id, game, platform, earned_at, proof_url, proof_msg_id),
        )
        await self.conn.commit()
        return cur.lastrowid

    async def adicionar_comprovantes(self, platina_id: int, comprovantes):
        """Armazena URLs de todos os comprovantes associados à platina."""
        for url, media_type in comprovantes:
            await self.conn.execute(
                "INSERT INTO platina_proofs(platina_id, proof_url, media_type) VALUES (?,?,?)",
                (platina_id, url, media_type),
            )
        await self.conn.commit()

    async def comprovantes_da_platina(self, platina_id: int):
        return await self._all(
            "SELECT proof_url, media_type FROM platina_proofs WHERE platina_id=? ORDER BY id",
            (platina_id,),
        )

    async def get_platina(self, platina_id: int):
        return await self._one("SELECT * FROM platinas WHERE id=?", (platina_id,))

    async def set_status(self, platina_id: int, status: str, reviewer_id: int):
        await self.conn.execute(
            "UPDATE platinas SET status=?, reviewer_id=? WHERE id=?",
            (status, reviewer_id, platina_id),
        )
        await self.conn.commit()

    async def decidir_platina(self, platina_id: int, status: str, reviewer_id: int) -> bool:
        """Aprova/rejeita só se ainda estiver pendente. Devolve False se outro moderador chegou antes
        (evita recompensa em dobro quando dois moderadores clicam quase ao mesmo tempo)."""
        cur = await self.conn.execute(
            "UPDATE platinas SET status=?, reviewer_id=? WHERE id=? AND status='pending'",
            (status, reviewer_id, platina_id),
        )
        await self.conn.commit()
        return cur.rowcount == 1

    async def platinas_do_usuario(self, user_id: int):
        return await self._all(
            "SELECT * FROM platinas WHERE user_id=? AND status='approved' ORDER BY earned_at DESC",
            (user_id,),
        )

    async def contar_platinas(self, user_id: int) -> int:
        row = await self._one(
            "SELECT COUNT(*) AS c FROM platinas WHERE user_id=? AND status='approved'", (user_id,)
        )
        return row["c"]

    async def posicao_platinas(self, quantidade: int) -> int:
        row = await self._one(
            """SELECT COUNT(*)+1 AS p FROM (
                 SELECT user_id, COUNT(*) AS c FROM platinas WHERE status='approved'
                 GROUP BY user_id HAVING c > ?)""",
            (quantidade,),
        )
        return row["p"]

    # ---------- rankings ----------
    async def ranking_platinas(self, limite=10):
        return await self._all(
            """SELECT user_id, COUNT(*) AS valor FROM platinas WHERE status='approved'
               GROUP BY user_id ORDER BY valor DESC LIMIT ?""",
            (limite,),
        )

    async def ranking_xp(self, limite=10):
        return await self._all(
            "SELECT user_id, xp AS valor FROM users WHERE xp > 0 ORDER BY xp DESC LIMIT ?",
            (limite,),
        )

    async def ranking_mensal(self, mes: str, limite=10):
        """mes no formato AAAA-MM, baseado na data da conquista."""
        return await self._all(
            """SELECT user_id, COUNT(*) AS valor FROM platinas
               WHERE status='approved' AND substr(earned_at,1,7)=?
               GROUP BY user_id ORDER BY valor DESC LIMIT ?""",
            (mes, limite),
        )

    # ---------- zerados ----------
    async def zerado_duplicado(self, user_id: int, game: str, platform: str) -> bool:
        row = await self._one(
            "SELECT 1 FROM zerados WHERE user_id=? AND lower(game)=lower(?) AND lower(platform)=lower(?)",
            (user_id, game, platform),
        )
        return row is not None

    async def criar_zerado(self, user_id, game, platform, finished_at, comment="", xp=0, denarios=0) -> int:
        cur = await self.conn.execute(
            """INSERT INTO zerados(user_id, game, platform, finished_at, comment, xp_awarded, denarios_awarded)
               VALUES (?,?,?,?,?,?,?)""",
            (user_id, game, platform, finished_at, comment, xp, denarios),
        )
        await self.conn.commit()
        return cur.lastrowid

    async def get_zerado(self, zerado_id: int):
        return await self._one("SELECT * FROM zerados WHERE id=?", (zerado_id,))

    async def apagar_zerado(self, zerado_id: int):
        await self.conn.execute("DELETE FROM zerados WHERE id=?", (zerado_id,))
        await self.conn.commit()

    async def zerados_do_usuario(self, user_id: int):
        return await self._all(
            "SELECT * FROM zerados WHERE user_id=? ORDER BY finished_at DESC, id DESC", (user_id,)
        )

    async def contar_zerados(self, user_id: int) -> int:
        row = await self._one("SELECT COUNT(*) AS c FROM zerados WHERE user_id=?", (user_id,))
        return row["c"]

    async def contar_zerados_recentes(self, user_id: int) -> int:
        """Registros das últimas 24h (usado no limite diário de XP)."""
        row = await self._one(
            "SELECT COUNT(*) AS c FROM zerados WHERE user_id=? AND created_at >= datetime('now','-1 day')",
            (user_id,),
        )
        return row["c"]

    async def posicao_zerados(self, quantidade: int) -> int:
        row = await self._one(
            """SELECT COUNT(*)+1 AS p FROM (
                 SELECT user_id, COUNT(*) AS c FROM zerados GROUP BY user_id HAVING c > ?)""",
            (quantidade,),
        )
        return row["p"]

    async def ranking_zerados(self, limite=10):
        return await self._all(
            "SELECT user_id, COUNT(*) AS valor FROM zerados GROUP BY user_id ORDER BY valor DESC LIMIT ?",
            (limite,),
        )

    async def ranking_zerados_mensal(self, mes: str, limite=10):
        """mes no formato AAAA-MM, baseado na data em que o jogo foi zerado."""
        return await self._all(
            """SELECT user_id, COUNT(*) AS valor FROM zerados
               WHERE substr(finished_at,1,7)=? GROUP BY user_id ORDER BY valor DESC LIMIT ?""",
            (mes, limite),
        )

    # ---------- loja (itens cosméticos comprados com Denários) ----------
    async def comprar_item(self, user_id: int, item: str, tipo: str, preco: int) -> str:
        """'ok', 'ja_tem' ou 'sem_saldo'. O débito só acontece se houver saldo (UPDATE condicional)."""
        await self.get_user(user_id)
        cur = await self.conn.execute(
            "INSERT OR IGNORE INTO inventario(user_id, item, tipo) VALUES (?,?,?)", (user_id, item, tipo))
        if cur.rowcount != 1:
            await self.conn.commit()
            return "ja_tem"
        cur = await self.conn.execute(
            "UPDATE users SET denarios = denarios - ? WHERE user_id=? AND denarios >= ?", (preco, user_id, preco))
        if cur.rowcount != 1:
            await self.conn.execute("DELETE FROM inventario WHERE user_id=? AND item=?", (user_id, item))
            await self.conn.commit()
            return "sem_saldo"
        await self.conn.commit()
        return "ok"

    async def inventario_do_usuario(self, user_id: int):
        return await self._all("SELECT item, tipo, equipado FROM inventario WHERE user_id=?", (user_id,))

    async def equipar_item(self, user_id: int, item: str, tipo: str) -> bool:
        """Equipa um item que a pessoa possui, desequipando o outro do mesmo tipo."""
        if await self._one("SELECT 1 FROM inventario WHERE user_id=? AND item=?", (user_id, item)) is None:
            return False
        await self.conn.execute("UPDATE inventario SET equipado=0 WHERE user_id=? AND tipo=?", (user_id, tipo))
        await self.conn.execute("UPDATE inventario SET equipado=1 WHERE user_id=? AND item=?", (user_id, item))
        await self.conn.commit()
        return True

    async def desequipar_tipo(self, user_id: int, tipo: str):
        await self.conn.execute("UPDATE inventario SET equipado=0 WHERE user_id=? AND tipo=?", (user_id, tipo))
        await self.conn.commit()

    # ---------- runs Soulslike: números para perfil/conquistas e recordes do Hall ----------
    async def stats_runs(self, user_id: int):
        """runs aprovadas e quantos recordes (melhor tempo geral de uma categoria) o usuário detém."""
        return await self._one(
            """SELECT
                 (SELECT COUNT(*) FROM sl_runs WHERE user_id=? AND status='approved') AS runs,
                 (SELECT COUNT(DISTINCT rec.game_id || '-' || rec.challenge_id)
                    FROM (SELECT game_id, challenge_id, MIN(seconds) AS m FROM sl_runs
                          WHERE status='approved' GROUP BY game_id, challenge_id) rec
                    JOIN sl_runs r ON r.game_id=rec.game_id AND r.challenge_id=rec.challenge_id
                                  AND r.seconds=rec.m AND r.status='approved' AND r.user_id=?) AS recordes""",
            (user_id, user_id),
        )

    async def recordes_recentes(self, limite: int = 6):
        """Um recorde por categoria (jogo + desafio), os mais recentes primeiro."""
        return await self._all(
            """SELECT g.name AS jogo, c.name AS desafio, r.user_id, r.seconds
               FROM sl_runs r
               JOIN sl_games g ON g.id=r.game_id JOIN sl_challenges c ON c.id=r.challenge_id
               WHERE r.status='approved'
                 AND r.id = (SELECT r2.id FROM sl_runs r2
                             WHERE r2.game_id=r.game_id AND r2.challenge_id=r.challenge_id AND r2.status='approved'
                             ORDER BY r2.seconds ASC, r2.id ASC LIMIT 1)
               ORDER BY r.id DESC LIMIT ?""",
            (limite,),
        )

    # ---------- painel do canal #colizeu ----------
    async def ranking_completo(self, limite=10):
        return await self._all(
            """SELECT p.user_id, COUNT(*) AS platinas, COALESCE(u.xp, 0) AS xp
               FROM platinas p LEFT JOIN users u ON u.user_id = p.user_id
               WHERE p.status='approved'
               GROUP BY p.user_id ORDER BY platinas DESC, xp DESC LIMIT ?""",
            (limite,),
        )

    async def ultimas_platinas(self, user_id: int, n: int = 3):
        return await self._all(
            """SELECT * FROM platinas WHERE user_id=? AND status='approved'
               ORDER BY earned_at DESC, id DESC LIMIT ?""",
            (user_id, n),
        )

    async def get_kv(self, key: str):
        row = await self._one("SELECT value FROM kv WHERE key=?", (key,))
        return row["value"] if row else None

    async def set_kv(self, key: str, value: str):
        await self.conn.execute(
            "INSERT INTO kv(key, value) VALUES (?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, value),
        )
        await self.conn.commit()

    # ---------- santuários (perfil em thread privada) ----------
    async def get_perfil(self, user_id: int):
        return await self._one("SELECT * FROM perfis WHERE user_id=?", (user_id,))

    async def get_perfil_por_thread(self, thread_id: int):
        return await self._one("SELECT * FROM perfis WHERE thread_id=?", (thread_id,))

    async def criar_perfil(self, user_id: int, thread_id: int):
        await self.conn.execute(
            "INSERT OR REPLACE INTO perfis(user_id, thread_id) VALUES (?,?)", (user_id, thread_id)
        )
        await self.conn.commit()

    async def atualizar_perfil(self, user_id: int, **campos):
        permitidos = {"card_msg_id", "tagline", "bio", "fav_game", "theme", "links", "thread_id"}
        campos = {k: v for k, v in campos.items() if k in permitidos}
        if not campos:
            return
        sets = ", ".join(f"{k}=?" for k in campos)
        await self.conn.execute(f"UPDATE perfis SET {sets} WHERE user_id=?", (*campos.values(), user_id))
        await self.conn.commit()

    async def apagar_perfil(self, user_id: int):
        await self.conn.execute("DELETE FROM perfis WHERE user_id=?", (user_id,))
        await self.conn.commit()
