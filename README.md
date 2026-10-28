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
- Pré-visualizar uma organização e aplicar um plano **não destrutivo**, que cria recursos ausentes sem renomear, mover ou excluir canais existentes.
- Configurar o recrutamento padrão para novos clãs, publicar/atualizar o painel público e diagnosticar/reparar recursos de clãs.
- Consultar diagnóstico e histórico, além de criar um ZIP de backup consistente dos bancos SQLite disponíveis.

O `.env` continua sendo necessário para segredos, caminhos e parâmetros de infraestrutura. O painel não consegue criar permissões que o próprio bot não possui.

## Catálogo de jogos, mods e notícias

Os comandos existentes do catálogo foram movidos para a aplicação principal. Entre os comandos preservados estão `/catalogo`, `/mods`, `/enviarmod`, `/adicionarmod` e `/painelmods`, além dos comandos de notícias RSS. Execute `/catalogo` no canal em que o painel deverá ficar e use os próprios comandos/painéis de administração para gerenciar conteúdo. O banco de catálogo permanece em `data/jogos.db` por padrão; capas e mods são persistidos no diretório de dados.

## Sistema de Clãs — Salão dos Juramentos

Na seção **Sistema de Clãs** do `/adm`, selecione o canal de destino e publique/atualize o painel **Salão dos Juramentos**. Recursos principais:

- Um clã criado por usuário e servidor, mesmo após encerramento; um vínculo de clã ativo por usuário/servidor.
- Limite de dez integrantes incluindo o líder, validado por transação e trigger SQLite.
- Nome, sigla, descrição, jogo principal, estilo, líder/oficiais/integrantes e recrutamento por convite/candidatura/misto.
- Convites expiráveis, candidaturas e gestão de membros por ações privadas.
- Categoria privada com canais de conversa, anúncios, estratégias e voz; membros e cargos autorizados recebem permissões específicas.
- Saída, transferência de liderança e encerramento com confirmação. Os registros históricos de membros e atividades não são eliminados simplesmente porque recursos do Discord foram excluídos.
- Diagnóstico e tentativa de reparo de categorias/canais ausentes via `/adm`.

A privacidade não é absoluta contra administradores do servidor ou cargos com permissões suficientes. Confirme as permissões efetivas da guild antes de disponibilizar os canais privados. A hierarquia do bot deve permitir que ele gerencie canais e permissões.

**A progressão competitiva dos clãs não concede XP/recompensas automáticas nesta versão.** O ranking de clãs é provisório (atividades marcadas como concluídas e tamanho do clã); regras definitivas de XP, recompensas e critérios de conclusão ainda precisam ser definidas antes de ativar uma disputa competitiva. A tela de atividades permite criá-las; uma interface de conclusão de atividades não está completa.

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
- O organizador do servidor aplica apenas criação de categorias/canais ausentes. Renomear, mover, consolidar ou remover recursos existentes exige plano separado e confirmação; isso foi deliberadamente evitado para não apagar histórico ou quebrar referências silenciosamente.
- A centralização de ativações/desativações já bloqueia novas interações do Sistema de Clãs. Algumas telas de módulo são informativas; desligamento integral por flag de todos os módulos ainda não está conectado a todos os listeners/tarefas.
- Ainda há etapas que exigem validação real de permissões, intents e credenciais externas no Developer Portal/hospedagem.
