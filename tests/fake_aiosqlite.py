"""Substituto mínimo do aiosqlite (sobre sqlite3) só para testar database.py sem instalar nada."""
import sqlite3
import sys
import types


class _Cursor:
    """Cursor com fetch assíncrono, como o do aiosqlite."""

    def __init__(self, cur):
        self._cur = cur
        self.lastrowid = cur.lastrowid
        self.rowcount = cur.rowcount

    async def fetchone(self):
        return self._cur.fetchone()

    async def fetchall(self):
        return self._cur.fetchall()


class _Resultado:
    def __init__(self, cur):
        self._cur = _Cursor(cur)

    def __await__(self):
        async def _c():
            return self._cur
        return _c().__await__()

    async def __aenter__(self):
        return self._cur

    async def __aexit__(self, *a):
        return False


class _Conexao:
    row_factory = None

    def __init__(self, path):
        self._c = sqlite3.connect(path)

    def __setattr__(self, k, v):
        if k == "row_factory":
            self._c.row_factory = v
        object.__setattr__(self, k, v)

    def execute(self, sql, args=()):
        return _Resultado(self._c.execute(sql, args))

    async def executescript(self, sql):
        self._c.executescript(sql)

    async def commit(self):
        self._c.commit()

    async def rollback(self):
        self._c.rollback()

    async def close(self):
        self._c.close()

    @property
    def total_changes(self):
        return self._c.total_changes


async def connect(path):
    return _Conexao(path)


def instalar():
    mod = types.ModuleType("aiosqlite")
    mod.connect = connect
    mod.Row = sqlite3.Row
    mod.Connection = _Conexao
    sys.modules["aiosqlite"] = mod
