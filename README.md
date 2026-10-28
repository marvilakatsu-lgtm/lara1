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

Ao aplicar a organização pelo `/adm`, o bot publica/atualiza o painel persistente **Salão dos Juramentos** em `🛡️・clãs`. Recursos principais:

- Um clã criado por usuário e servidor, mesmo após encerramento; um vínculo de clã ativo por usuário/servidor.
- Limite de dez integrantes incluindo o líder, validado por transação e trigger SQLite.
- Nome, sigla, descrição, jogo principal, estilo, líder/oficiais/integrantes e recrutamento por convite/candidatura/misto.
- Convites expiráveis, candidaturas e gestão de membros por ações privadas.
- Categoria privada com canais de conversa, anúncios, estratégias e voz; membros e cargos autorizados recebem permissões específicas.
- Saída, transferência de liderança e encerramento com confirmação. Os registros históricos de membros e atividades não são eliminados simplesmente porque recursos do Discord foram excluídos.
- Diagnóstico e tentativa de reparo de categorias/canais ausentes via `/adm`.

A privacidade não é absoluta contra administradores do servidor ou cargos com permissões suficientes. Confirme as permissões efetivas da guild antes de disponibilizar os canais privados. A hierarquia do bot deve permitir que ele gerencie canais e permissões.

**A progressão competitiva dos clãs não concede XP/recompensas automáticas nesta versão.** O ranking de clãs é provisório (atividades marcadas como concluídas e tamanho do clã); regras definitivas de XP, recompensas e critérios de conclusão ainda precisam ser definidas antes de ativar uma disputa competitiva. A tela de atividades permite criá-las; uma interface de conclusão de atividades não está completa.

## Estrutura Quase Pro — versão simplificada

O plano foi reduzido de **10 para 8 categorias** e de **63 para 28 canais planejados**, incluindo os canais privados da equipe. A meta é orientar a comunidade rapidamente, não criar um canal para cada recurso interno do bot. Destinos de automações semelhantes compartilham o mesmo canal, mantendo suas chaves de configuração separadas para compatibilidade.

1. **`👋・INÍCIO`** — `👋・boas-vindas`, `📜・regras`, `✅・verificação`.
2. **`📣・QUASE PRO`** — `📣・avisos-e-vídeos`, `🔴・lives`, `💡・conteúdo-e-votações`.
3. **`💬・COMUNIDADE`** — `💬・chat-geral`, `😂・memes-e-clipes`, `🤝・procurando-jogadores`, `🎮・outros-jogos`, `💭・ajuda-e-sugestões`, `🎭・cargos-de-interesse`.
4. **`🎮・SOULSLIKE`** — `🌳・elden-ring`, `🔥・dark-souls`, `🌑・outros-soulslikes`, `🗡️・builds-e-chefes`, `🏆・runs-e-desafios`.
5. **`📚・CATÁLOGO`** — `📚・jogos-e-mods`, `🎁・ofertas-e-notícias`.
6. **`🏆・PROGRESSÃO E CLÃS`** — `🏅・perfis-e-conquistas`, `⚔️・coliseu-e-desafios`, `🛡️・clãs`.
7. **`🔊・VOZ`** — `🔊・papo-livre`, `🎮・coop-e-jogos`, `🎙️・eventos`.
8. **`🔒・EQUIPE`** (privada) — `💬・chat-da-equipe`, `📋・logs-e-auditoria`, `🎫・suporte-e-aprovações`.

### Como os canais foram consolidados

- Avisos gerais e notificações de novos vídeos compartilham `📣・avisos-e-vídeos`; lives continuam separadas para não misturar notificações de início de transmissão.
- Catálogo de jogos, catálogo de mods e envio de mods usam painéis separados no mesmo `📚・jogos-e-mods`.
- Jogos gratuitos, promoções e notícias compartilham `🎁・ofertas-e-notícias`.
- Perfis, jogos concluídos e platinas compartilham `🏅・perfis-e-conquistas`; Coliseu e runs/desafios compartilham `⚔️・coliseu-e-desafios`.
- A descoberta, o recrutamento, o ranking e os eventos de clãs são acessados pelo painel permanente em `🛡️・clãs`; cada clã mantém sua própria categoria privada, com conversa, anúncios, estratégias e voz.
- Ajuda, perguntas ao bot e sugestões ficam centralizadas em `💭・ajuda-e-sugestões`; os comandos slash continuam disponíveis nas áreas onde o membro tem permissão.

A aplicação reutiliza canais encontrados por nome/alias e preserva as mensagens ao renomear/mover canais. Canais antigos redundantes que sobrarem após a consolidação são movidos para `🗄️・ARQUIVO ANTIGO`, visível apenas à equipe; categorias antigas conhecidas são ocultadas. **Nenhum canal ou mensagem é excluído.** A equipe deve revisar o resultado após a execução, pois alterações de permissões não têm rollback automático garantido.

### Verificação e acesso

`👋・INÍCIO` é a única categoria visível antes da verificação e é somente leitura para não verificados. O novo membro lê as regras e clica no botão de verificação em `✅・verificação`; o bot atribui `🟢・Membro`. As demais categorias públicas ficam ocultas para `@everyone` e só abrem para o cargo verificado e a equipe autorizada. `🔒・EQUIPE` permanece privada. O bot precisa de **Gerenciar Canais** e **Gerenciar Cargos**, e seu cargo precisa estar acima do cargo `🟢・Membro`.

## Cargos, hierarquia e cores

O plano cria/atualiza **31 cargos funcionais com cores distintas**. A hierarquia correta é:

1. Equipe, de cima para baixo: `👑・Fundador` → `⚙️・Administrador` → `🛡️・Moderador` → `🎫・Equipe de Suporte` → `🔧・Desenvolvedor`.
2. Cargo real do bot — abaixo da equipe e acima dos cargos funcionais que o bot precisa administrar.
3. Patentes Soulslike, do nível mais alto para o inicial.
4. Cargos internos de clãs, sem permissões administrativas do servidor.
5. Cargos de comunidade (`Criador de Conteúdo`, `Aliado`, `Membro`, `Recém-chegado`).
6. Cargos de interesse e notificações.

O bot pode organizar automaticamente os cargos funcionais abaixo dele, mas não pode mover a equipe para cima do seu próprio cargo. Na primeira aplicação, coloque manualmente os cinco cargos de equipe acima do cargo real do bot na ordem indicada e execute `/adm` novamente para validar.

### Patentes e XP

Os nomes e critérios existentes no Soulsbot são preservados. O cargo é sincronizado com o XP/nível registrado; a organização não recalcula XP nem concede recompensas adicionais.

| Nível mínimo | Patente | Cor |
|---:|---|---:|
| 1 | `🪨・Cinzas Novatas` | `#7F8C8D` |
| 5 | `🩸・Guerreiro Caído` | `#8E6E53` |
| 10 | `💀・Caçador de Almas` | `#7B241C` |
| 15 | `⚔️・Cavaleiro do Abismo` | `#2E4053` |
| 20 | `🪶・Guardião das Cinzas` | `#566573` |
| 30 | `🌑・Arauto da Ruína` | `#6C3483` |
| 40 | `🔥・Executor Sombrio` | `#17202A` |
| 50 | `🌌・Senhor das Almas` | `#D35400` |
| 75 | `🏆・Lenda do Coliseu` | `#BA4A00` |
| 100 | `🌟・Sentinela Imortal` | `#F4D03F` |

### Cores dos demais cargos

| Cargo | Cor |
|---|---:|
| `👑・Fundador` | `#F1C40F` |
| `⚙️・Administrador` | `#E74C3C` |
| `🛡️・Moderador` | `#3498DB` |
| `🎫・Equipe de Suporte` | `#9B59B6` |
| `🔧・Desenvolvedor` | `#1ABC9C` |
| `👑・Líder de Clã` | `#AF7AC5` |
| `🗡️・Oficial de Clã` | `#4A235A` |
| `⚔️・Membro de Clã` | `#0E6251` |
| `📺・Criador de Conteúdo` | `#5DADE2` |
| `🤝・Aliado` | `#B7950B` |
| `🟢・Membro` | `#27AE60` |
| `🌱・Recém-chegado` | `#82E0AA` |
| `🎮・Elden Ring` | `#1F618D` |
| `🔥・Dark Souls` | `#884EA0` |
| `🩸・Bloodborne` | `#117864` |
| `🥷・Sekiro` | `#CD6155` |
| `🦾・Lies of P` | `#A93226` |
| `🌑・Nightreign` | `#2874A6` |
| `📹・Avisos de vídeos` | `#239B56` |
| `🔴・Avisos de lives` | `#CA6F1E` |
| `🏆・Eventos e desafios` | `#616A6B` |

As três antigas etiquetas decorativas de bot (`Soulsbot`, `Bot Catálogo`, `Bot Organizador`) não são mais criadas, pois os módulos usam uma única identidade de bot Discord. Se essas etiquetas já existirem no servidor, esta aplicação não as exclui automaticamente: confira se não têm membros ou overwrites associados antes de removê-las manualmente.

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

Validação local da versão comunitária simplificada: `compileall` concluído e 49 testes unitários aprovados. Isso não substitui o teste de interação com o bot conectado ao Discord nem a confirmação da API do YouTube com as credenciais da hospedagem.
