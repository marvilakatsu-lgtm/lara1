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
- Associar cargos administrativos e funcionais. A organização aplica perfis predefinidos aos cargos que consegue gerir; a atribuição dos cargos de equipe aos membros continua manual. O cargo Fundador possui a permissão Administrador e deve ser atribuído com cautela.
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

A opção `/adm` → Organização do servidor aplica **10 categorias e 63 canais**, na ordem abaixo. Canais existentes encontrados por nome/alias são reutilizados, renomeados e movidos; o histórico da mensagem permanece porque o canal não é excluído.

1. `🔥・PORTÕES DO SANTUÁRIO`: `📜・boas-vindas`, `📕・regras-do-reino`, `✅・verificação`, `📢・anúncios-importantes`, `🎭・escolha-seus-cargos`, `🧭・guia-do-servidor`.
2. `🎬・QUASE PRO`: `📣・avisos-do-canal`, `🎥・novos-vídeos`, `🔴・lives-ao-vivo`, `💡・sugestões-de-vídeos`, `🗳️・votações-da-comunidade`, `🎬・bastidores-do-quase-pro`.
3. `🏰・PRAÇA DOS MACULADOS`: `💬・bate-papo`, `👋・apresente-se`, `😂・memes-do-reino`, `📸・prints-e-clipes`, `🤝・procurando-jogadores`, `🎮・outros-jogos` (texto), `💭・sugestões-do-servidor`.
4. `⚔️・TERRAS SOULSLIKE`: `🌳・elden-ring`, `🔥・dark-souls`, `🛡️・dark-souls-ii`, `⚔️・dark-souls-iii`, `🩸・bloodborne`, `🥷・sekiro`, `👑・demon-souls`, `🦾・lies-of-p`, `🌑・nightreign`, `🗡️・builds-e-armas`, `💀・chefes-e-estratégias`, `🏆・runs-e-desafios`, `📖・lore-e-teorias`.
5. `🏆・COLISEU DAS CINZAS`: `🏟️・hall-do-coliseu`, `📊・ranking-de-zerados`, `💎・hall-das-platinas`, `🎖️・perfis-e-patentes`, `🔥・santuários`, `📜・runs-registradas`, `🥇・conquistas-da-comunidade`.
6. `📚・ARQUIVO DO VIAJANTE`: `🎮・catálogo-de-jogos`, `🧩・catálogo-de-mods`, `📥・envio-de-mods`, `📰・notícias-gamer`, `🎁・jogos-grátis`, `💰・promoções-gamer`.
7. `🤖・ORÁCULO DO SANTUÁRIO`: `🧠・pergunte-à-ia`, `📘・central-de-ajuda`, `🎫・abrir-suporte`.
8. `🛡️・SALÃO DOS JURAMENTOS`: `⚔️・painel-de-clãs`, `📜・recrutamento-de-clãs`, `🏅・ranking-de-clãs`, `📅・eventos-de-clãs`.
9. `🔊・FOGUEIRAS DA COMUNIDADE` (voz): `🔥・papo-livre`, `🤝・coop-souls`, `⚔️・arena-pvp`, `🎮・outros-jogos`, `🎙️・sala-de-eventos`.
10. `🔒・BASTIDORES DA ORDEM` (privada): `💬・chat-da-equipe`, `🛡️・logs-de-moderação`, `🤖・logs-dos-bots`, `⚙️・comandos-adm`, `🎫・relatórios-de-suporte`, `📋・auditoria-de-clãs`.

A aplicação publica/atualiza o painel de verificação em `✅・verificação`, o painel de escolha de cargos, os painéis do catálogo de jogos/mods e o Salão dos Juramentos, desde que os canais existam e o bot tenha permissão para enviar mensagens.

### Bloqueio de acesso até a verificação

A categoria `🔥・PORTÕES DO SANTUÁRIO` fica visível a todos para que novos membros possam ler regras e usar o botão em `✅・verificação`. As outras oito categorias públicas recebem `@everyone: view_channel=False` e `🟢・Membro: view_channel=True`; o bot e cargos autorizados de equipe também têm acesso explícito. A categoria `🔒・BASTIDORES DA ORDEM` mantém ACL privada de equipe. A verificação só libera as áreas restantes quando o bot consegue atribuir o cargo Membro. Antes de aplicar, confira se o cargo do bot está acima de `🟢・Membro` e se tem `Gerenciar Canais` e `Gerenciar Cargos`. Pessoas com `Administrador` no Discord podem ignorar overwrites de canal, como esperado.

## Cargos, paleta e patentes por XP

A organização cria/atualiza 34 cargos gerenciados pelo projeto com **34 cores hexadecimais únicas**. Os cargos de fundador, administrador e moderador recebem os perfis definidos no código; suporte, desenvolvedor, clãs, comunidade, interesses e etiquetas técnicas não recebem permissões administrativas.

### Hierarquia correta — de cima para baixo

1. `👑・Fundador`
2. `⚙️・Administrador`
3. `🛡️・Moderador`
4. `🎫・Equipe de Suporte`
5. `🔧・Desenvolvedor`
6. **Cargo real da aplicação/bot no Discord** — fronteira da hierarquia; deve ficar abaixo da equipe e acima dos cargos que o bot administra.
7. **Patentes, do nível mais alto ao inicial:** `🌟・Sentinela Imortal` (nível 100), `🏆・Lenda do Coliseu` (75), `🌌・Senhor das Almas` (50), `🔥・Executor Sombrio` (40), `🌑・Arauto da Ruína` (30), `🪶・Guardião das Cinzas` (20), `⚔️・Cavaleiro do Abismo` (15), `💀・Caçador de Almas` (10), `🩸・Guerreiro Caído` (5), `🪨・Cinzas Novatas` (1).
8. Cargos de clã: `👑・Líder de Clã` > `🗡️・Oficial de Clã` > `⚔️・Membro de Clã`.
9. Comunidade: `📺・Criador de Conteúdo` e `🤝・Aliado` > `🟢・Membro` > `🌱・Recém-chegado`.
10. Interesses/notificações e etiquetas técnicas ficam na base.

**Limite da API do Discord:** um bot não pode mover cargos para cima do seu maior cargo nem editar cargos acima dele. Na primeira aplicação, o bot padroniza os cargos e ordena automaticamente os cargos funcionais abaixo de si; você precisa mover manualmente os cinco cargos de equipe para cima do cargo real do bot, nesta ordem exata: Fundador > Administrador > Moderador > Equipe de Suporte > Desenvolvedor. Não atribua cargos privilegiados a ninguém até terminar esse passo. Execute `/adm` novamente para validar a hierarquia. A seção Diagnóstico também sinaliza cargos funcionais posicionados no lado errado do cargo do bot.

A hierarquia de patentes agora é ordenada pelo nível mínimo em ordem decrescente, não pela ordem de criação. Assim, `Sentinela Imortal` fica acima das demais patentes, enquanto `Cinzas Novatas` fica abaixo delas. O XP e os requisitos existentes não são alterados.

### Paleta completa dos 34 cargos

| Cargo | Grupo | Cor |
|---|---|---:|
| 👑・Fundador | staff | `#F1C40F` |
| ⚙️・Administrador | staff | `#E74C3C` |
| 🛡️・Moderador | staff | `#3498DB` |
| 🎫・Equipe de Suporte | staff | `#9B59B6` |
| 🔧・Desenvolvedor | staff | `#1ABC9C` |
| 🌟・Sentinela Imortal | rank | `#F4D03F` |
| 🏆・Lenda do Coliseu | rank | `#BA4A00` |
| 🌌・Senhor das Almas | rank | `#D35400` |
| 🔥・Executor Sombrio | rank | `#17202A` |
| 🌑・Arauto da Ruína | rank | `#6C3483` |
| 🪶・Guardião das Cinzas | rank | `#566573` |
| ⚔️・Cavaleiro do Abismo | rank | `#2E4053` |
| 💀・Caçador de Almas | rank | `#7B241C` |
| 🩸・Guerreiro Caído | rank | `#8E6E53` |
| 🪨・Cinzas Novatas | rank | `#7F8C8D` |
| 👑・Líder de Clã | clan | `#AF7AC5` |
| 🗡️・Oficial de Clã | clan | `#4A235A` |
| ⚔️・Membro de Clã | clan | `#0E6251` |
| 📺・Criador de Conteúdo | community | `#5DADE2` |
| 🤝・Aliado | community | `#B7950B` |
| 🟢・Membro | community | `#27AE60` |
| 🌱・Recém-chegado | community | `#82E0AA` |
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

## Correção adicional — catálogo e feed do YouTube (28/10/2026)

- Corrigido o callback **Catálogo de jogos**: `cogs/catalogo.py` agora omite o argumento `file` quando a grade/capa não produz um anexo. Isso evita o `AttributeError: 'NoneType' object has no attribute 'to_dict'` no envio da interação.
- Corrigido o mesmo padrão no fluxo de busca de jogos, que também podia enviar `file=None` quando a busca não tinha resultados ou não havia imagem.
- O aviso HTTP 404 do feed do YouTube é separado do erro do catálogo. O bot continua tentando o fallback pela API quando a chave está configurada. O log agora esclarece que o 404 pode ser temporário ou indicar `YOUTUBE_CHANNEL_ID` incorreto e limita avisos repetidos a um por 15 minutos.
- Se o RSS falhar e `YOUTUBE_API_KEY` não estiver configurada, o bot registra essa limitação explicitamente. O ID deve ser o ID canônico do canal (`UC` seguido de 22 caracteres), não o nome `@handle` ou uma URL.

Validação local após a correção de hierarquia dos cargos: `compileall` concluído e 47 testes unitários aprovados. Isso não substitui o teste de interação com o bot conectado ao Discord nem a confirmação da API do YouTube com as credenciais da hospedagem.
