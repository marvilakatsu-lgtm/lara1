# Quase Pro — aplicação integrada de Discord

Repositório consolidado do Soulsbot, catálogo de jogos/mods e Sistema de Clãs. A aplicação usa **um único cliente Discord autenticado** e um ponto de inicialização (`python bot.py`). Os bancos SQLite permanecem separados para não fazer uma fusão arriscada de esquemas e dados históricos.

## Requisitos

- Python 3.11 ou mais recente (recomendado: Python 3.12).
- `discord.py` 2.7 ou mais recente, além das dependências de `requirements.txt`.
- Aplicação de bot no [Discord Developer Portal](https://discord.com/developers/applications), com token válido.
- Para os módulos existentes que usam essas funções, habilite **Server Members Intent**, **Message Content Intent** e **Voice States Intent** no Developer Portal.
- Permissões de servidor compatíveis com os recursos ativados. Para o funcionamento completo: Ver canais, Ler histórico, Enviar mensagens, Incorporar links, Anexar arquivos, Gerenciar canais, Gerenciar permissões/cargos e permissões de threads; limite o acesso da equipe conforme a política do servidor.

## Instalação

Linux/macOS:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp env.example .env
```

Windows PowerShell:

```powershell
py -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item env.example .env
```

Edite `.env` e preencha pelo menos `DISCORD_TOKEN`. Acrescente `YOUTUBE_API_KEY` e `GEMINI_API_KEY` somente quando os respectivos módulos forem usados. **Não coloque tokens em mensagens do Discord ou em logs, e nunca publique `.env`.**

Inicie a aplicação:

```bash
python bot.py
```

Não inicie o `cogs/catalogo.py` separadamente. O catálogo foi carregado como extensão do cliente principal; iniciar o arquivo antigo à parte criaria dois processos e poderia duplicar eventos.

## Migração de uma instalação existente

Os ZIPs recebidos continham código-fonte, mas **não incluíam bancos de dados SQLite nem todos os dados de produção**. Antes de substituir o bot que está em execução:

1. Pare o processo antigo.
2. Faça uma cópia de segurança de todos os bancos, capas, imagens e arquivos persistentes do catálogo.
3. Copie o banco do Soulsbot/Coliseu para `data/colizeu.db`, o banco do catálogo para `data/jogos.db`, e o banco de controle de ofertas para `data/sent_offers.sqlite3` (ajuste caminhos em `.env` quando necessário).
4. Preserve os nomes relativos de capas e mods gravados no banco; por padrão, os arquivos ficam na pasta persistente configurada por `DATA_DIR`/`CATALOGO_DATA_DIR`.
5. Inicie a nova aplicação e confira os logs antes de desativar definitivamente o ambiente antigo.

O esquema principal é ampliado de forma não destrutiva na inicialização. O catálogo mantém seu próprio banco (`CATALOGO_DB_PATH`). A camada de configurações por servidor importa IDs de variáveis antigas quando eles são inteiros válidos, o recurso existe naquele servidor e a configuração ainda não foi salva no painel. Valores já persistidos pelo `/adm` não são sobrescritos.

## Configuração pelo Discord

Use `/adm` com uma conta que possua **Gerenciar Servidor**, **Administrador** ou um cargo definido como cargo administrativo autorizado. O painel é efêmero, revalida o acesso em cada ação e grava as alterações e operações administrativas no banco principal.

O painel permite:

- Associar canais de texto aos sistemas e categorias existentes por seletores nativos do Discord.
- Associar cargos administrativos e funcionais.
- Escolher as categorias funcionais do servidor.
- Pré-visualizar uma organização e aplicar o plano oficial Quase Pro: reaproveita canais por nome/aliases, renomeia e move canais para as categorias corretas preservando mensagens, cria recursos ausentes e ajusta permissões. Não exclui canais, mensagens, cargos ou dados; a aplicação pode ser parcial se o bot não tiver permissões/hierarquia suficiente.
- Configurar o recrutamento padrão para novos clãs, publicar/atualizar o painel público e diagnosticar/reparar recursos de clãs.
- Consultar diagnóstico e histórico, além de criar um ZIP de backup consistente dos bancos SQLite disponíveis.

O `.env` continua sendo necessário para segredos, caminhos e parâmetros de infraestrutura. O painel não consegue criar permissões que o próprio bot não possui.

## Catálogo de jogos, mods e notícias

Os comandos existentes do catálogo foram movidos para a aplicação principal. Entre os comandos preservados estão `/catalogo`, `/mods`, `/enviarmod`, `/adicionarmod` e `/painelmods`, além dos comandos de notícias RSS. Execute `/catalogo` no canal em que o painel deverá ficar e use os próprios comandos/painéis de administração para gerenciar conteúdo. O banco de catálogo permanece em `data/jogos.db` por padrão; capas e mods são persistidos no diretório de dados.

## Sistema de Clãs — Salão dos Juramentos

Ao aplicar a organização pelo `/adm`, o bot publica/atualiza o painel persistente **Salão dos Juramentos** em `⚔️・painel-de-clãs`. Recursos principais:

- Um clã criado por usuário e servidor, mesmo após encerramento; um vínculo de clã ativo por usuário/servidor.
- Limite de dez integrantes incluindo o líder, validado por transação e trigger SQLite.
- Nome, sigla, descrição, jogo principal, estilo, líder/oficiais/integrantes e recrutamento por convite/candidatura/misto.
- Convites expiráveis, candidaturas e gestão de membros por ações privadas.
- Categoria privada com canais de conversa, anúncios, estratégias e voz; membros e cargos autorizados recebem permissões específicas.
- Saída, transferência de liderança e encerramento com confirmação. Os registros históricos de membros e atividades não são eliminados simplesmente porque recursos do Discord foram excluídos.
- Diagnóstico e tentativa de reparo de categorias/canais ausentes via `/adm`.

A privacidade não é absoluta contra administradores do servidor ou cargos com permissões suficientes. Confirme as permissões efetivas da guild antes de disponibilizar os canais privados. A hierarquia do bot deve permitir que ele gerencie canais e permissões.

**A progressão competitiva dos clãs não concede XP/recompensas automáticas nesta versão.** O ranking de clãs é provisório (atividades marcadas como concluídas e tamanho do clã); regras definitivas de XP, recompensas e critérios de conclusão ainda precisam ser definidas antes de ativar uma disputa competitiva. A tela de atividades permite criá-las; uma interface de conclusão de atividades não está completa.

## Estrutura Quase Pro — organização oficial

A opção `/adm` → Organização do servidor aplica **10 categorias e 62 canais**, na ordem abaixo. Canais existentes encontrados por nome/alias são reutilizados, renomeados e movidos; o histórico da mensagem permanece porque o canal não é excluído.

1. `🔥・PORTÕES DO SANTUÁRIO`: `📜・boas-vindas`, `📕・regras-do-reino`, `📢・anúncios-importantes`, `🎭・escolha-seus-cargos`, `🧭・guia-do-servidor`.
2. `🎬・QUASE PRO`: `📣・avisos-do-canal`, `🎥・novos-vídeos`, `🔴・lives-ao-vivo`, `💡・sugestões-de-vídeos`, `🗳️・votações-da-comunidade`, `🎬・bastidores-do-quase-pro`.
3. `🏰・PRAÇA DOS MACULADOS`: `💬・bate-papo`, `👋・apresente-se`, `😂・memes-do-reino`, `📸・prints-e-clipes`, `🤝・procurando-jogadores`, `🎮・outros-jogos` (texto), `💭・sugestões-do-servidor`.
4. `⚔️・TERRAS SOULSLIKE`: `🌳・elden-ring`, `🔥・dark-souls`, `🛡️・dark-souls-ii`, `⚔️・dark-souls-iii`, `🩸・bloodborne`, `🥷・sekiro`, `👑・demon-souls`, `🦾・lies-of-p`, `🌑・nightreign`, `🗡️・builds-e-armas`, `💀・chefes-e-estratégias`, `🏆・runs-e-desafios`, `📖・lore-e-teorias`.
5. `🏆・COLISEU DAS CINZAS`: `🏟️・hall-do-coliseu`, `📊・ranking-de-zerados`, `💎・hall-das-platinas`, `🎖️・perfis-e-patentes`, `🔥・santuários`, `📜・runs-registradas`, `🥇・conquistas-da-comunidade`.
6. `📚・ARQUIVO DO VIAJANTE`: `🎮・catálogo-de-jogos`, `🧩・catálogo-de-mods`, `📥・envio-de-mods`, `📰・notícias-gamer`, `🎁・jogos-grátis`, `💰・promoções-gamer`.
7. `🤖・ORÁCULO DO SANTUÁRIO`: `🧠・pergunte-à-ia`, `📘・central-de-ajuda`, `🎫・abrir-suporte`.
8. `🛡️・SALÃO DOS JURAMENTOS`: `⚔️・painel-de-clãs`, `📜・recrutamento-de-clãs`, `🏅・ranking-de-clãs`, `📅・eventos-de-clãs`.
9. `🔊・FOGUEIRAS DA COMUNIDADE` (voz): `🔥・papo-livre`, `🤝・coop-souls`, `⚔️・arena-pvp`, `🎮・outros-jogos`, `🎙️・sala-de-eventos`.
10. `🔒・BASTIDORES DA ORDEM` (privada): `💬・chat-da-equipe`, `🛡️・logs-de-moderação`, `🤖・logs-dos-bots`, `⚙️・comandos-adm`, `🎫・relatórios-de-suporte`, `📋・auditoria-de-clãs`.

A aplicação publica/atualiza os painéis persistentes de boas-vindas, escolha de cargos, catálogo de jogos, catálogo/envio de mods e Salão dos Juramentos, desde que os canais existam e o bot tenha permissão para enviar mensagens.

## Cargos, paleta e patentes por XP

A organização cria/atualiza 34 cargos gerenciados pelo projeto com **34 cores hexadecimais únicas**. Os cargos de fundador, administrador e moderador recebem apenas os perfis de permissão definidos no código; suporte, desenvolvedor, clãs, comunidade, interesses e etiquetas técnicas não recebem permissões administrativas. O cargo do bot deve estar acima dos cargos que precisa gerenciar.

### Paleta completa dos 34 cargos

| Cargo | Grupo | Cor |
|---|---|---:|
| 👑・Fundador | staff | `#F1C40F` |
| ⚙️・Administrador | staff | `#E74C3C` |
| 🛡️・Moderador | staff | `#3498DB` |
| 🎫・Equipe de Suporte | staff | `#9B59B6` |
| 🔧・Desenvolvedor | staff | `#1ABC9C` |
| 🪨・Cinzas Novatas | rank | `#7F8C8D` |
| 🩸・Guerreiro Caído | rank | `#8E6E53` |
| 💀・Caçador de Almas | rank | `#7B241C` |
| ⚔️・Cavaleiro do Abismo | rank | `#2E4053` |
| 🪶・Guardião das Cinzas | rank | `#566573` |
| 🌑・Arauto da Ruína | rank | `#6C3483` |
| 🔥・Executor Sombrio | rank | `#17202A` |
| 🌌・Senhor das Almas | rank | `#D35400` |
| 🏆・Lenda do Coliseu | rank | `#BA4A00` |
| 🌟・Sentinela Imortal | rank | `#F4D03F` |
| 👑・Líder de Clã | clan | `#AF7AC5` |
| 🗡️・Oficial de Clã | clan | `#4A235A` |
| ⚔️・Membro de Clã | clan | `#0E6251` |
| 🌱・Recém-chegado | community | `#82E0AA` |
| 🟢・Membro | community | `#27AE60` |
| 📺・Criador de Conteúdo | community | `#5DADE2` |
| 🤝・Aliado | community | `#B7950B` |
| 🎮・Elden Ring | interest | `#1F618D` |
| 🔥・Dark Souls | interest | `#884EA0` |
| 🩸・Bloodborne | interest | `#117864` |
| 🥷・Sekiro | interest | `#CD6155` |
| 🦾・Lies of P | interest | `#A93226` |
| 🌑・Nightreign | interest | `#2874A6` |
| 📹・Avisos de vídeos | interest | `#239B56` |
| 🔴・Avisos de lives | interest | `#CA6F1E` |
| 🏆・Eventos e desafios | interest | `#616A6B` |
| 🤖・Soulsbot | technical | `#A3E4D7` |
| 📚・Bot Catálogo | technical | `#F5B7B1` |
| ⚙️・Bot Organizador | technical | `#FAD7A0` |

Os cargos de interesse configurados no painel `🎭・escolha-seus-cargos` são: Elden Ring, Dark Souls, Bloodborne, Sekiro, Lies of P, Nightreign, avisos de vídeos, avisos de lives e eventos/desafios. O painel pode adicionar/remover esses cargos; patentes não são selecionadas manualmente.

O vínculo entre nível e patente usa os critérios que já existiam no Soulsbot, sem alterar XP:

| Nível mínimo | Cargo de patente |
|---:|---|
| 1 | `🪨・Cinzas Novatas` |
| 5 | `🩸・Guerreiro Caído` |
| 10 | `💀・Caçador de Almas` |
| 15 | `⚔️・Cavaleiro do Abismo` |
| 20 | `🪶・Guardião das Cinzas` |
| 30 | `🌑・Arauto da Ruína` |
| 40 | `🔥・Executor Sombrio` |
| 50 | `🌌・Senhor das Almas` |
| 75 | `🏆・Lenda do Coliseu` |
| 100 | `🌟・Sentinela Imortal` |

Ao receber XP e ao entrar no servidor, o Soulsbot calcula o nível e sincroniza o cargo correto; ao aplicar a estrutura, tenta também reconciliar os usuários já registrados no banco. Isso depende de o cargo estar abaixo do cargo mais alto do bot e de `Gerenciar Cargos` estar habilitado.

As três etiquetas técnicas (`🤖・Soulsbot`, `📚・Bot Catálogo`, `⚙️・Bot Organizador`) são criadas sem permissões. Como o código integrado agora opera com **uma única identidade de bot Discord**, essas etiquetas não isolam permissões por módulo nem representam três contas distintas.

## Comandos Soulsbot preservados

Os módulos originais do projeto incluem perfis, XP/níveis/patentes, platinas e aprovações, Coliseu, ranking, cargos, Sentinela, YouTube, jogos gratuitos/ofertas, zerados, santuários, runs/desafios Soulslike, loja e Nexus AI. Os canais/cargos operacionais que foram ligados à configuração central consultam as associações salvas por servidor. Tokens e configurações que não podem ser representados por seletores nativos permanecem no ambiente.

## Backup e restauração

A seção **Backup e restauração** do `/adm` gera um ZIP com snapshots SQLite dos bancos que existirem nos caminhos configurados. Como esse arquivo pode conter IDs de usuários, submissões e estatísticas, mantenha-o com acesso restrito.

A interface de **restauração automática ainda não foi implementada**. Para restaurar: pare o bot, preserve cópia do estado atual, extraia os bancos do ZIP para os caminhos corretos, confira permissões de arquivo e reinicie. Não sobrescreva bancos ativos com o processo em execução.

## Testes e validação

Execute os testes unitários offline:

```bash
python -m compileall -q bot.py config.py database.py settings_store.py cogs tests
python -m unittest discover -s tests -v
```

Os testes cobrem regras centrais de banco, progressão, cartões, isolamento de configurações por servidor e bloqueio do 11º integrante. Eles **não** simulam toda a API do Discord nem substituem uma implantação de teste com o bot conectado. Antes de produção, valide manualmente `/adm`, seletor de canais/cargos, publicação do catálogo, submissões, aprovação, criação de clã, entrada/saída de membros e exclusão manual de recursos num servidor de teste.

## Limitações conhecidas desta entrega

- Não foi possível realizar login real no Discord nem testar interações end-to-end nesta sessão, por falta de token/permissões e indisponibilidade das dependências no ambiente de execução.
- O organizador renomeia e move canais correspondentes por nome/aliases, e altera overwrites das categorias públicas e privadas para implementar o plano. Ele nunca exclui canais ou mensagens. Mudanças de permissões no Discord não possuem rollback automático garantido; faça uma revisão do plano e backup dos bancos antes de aplicar.
- A centralização de ativações/desativações já bloqueia novas interações do Sistema de Clãs. Algumas telas de módulo são informativas; desligamento integral por flag de todos os módulos ainda não está conectado a todos os listeners/tarefas.
- Ainda há etapas que exigem validação real de permissões, intents e credenciais externas no Developer Portal/hospedagem.
