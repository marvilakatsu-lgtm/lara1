# Relatório de auditoria e implementação — Quase Pro

**Escopo:** arquivos `soulsbot-melhorado (1)(2).zip`, `botcatalogo-main(4).zip` e requisitos anexados em texto.  
**Resultado desta entrega:** integração de código-fonte, novas camadas de configuração e clãs, testes unitários locais. Não houve conexão real a um servidor Discord nesta sessão.

## 1. Inventário original

### Soulsbot

O projeto é Python, usa `discord.py` com extensões em `cogs/`, SQLite por `aiosqlite`, configurações em `config.py`/ambiente e testes unitários. Os módulos encontrados no código incluem:

- Perfis e cartões, XP/níveis/patentes, loja e inventário cosmético.
- Registro e aprovação de platinas, comprovantes e anúncios.
- Jogos zerados, rankings, conquistas calculadas a partir dos registros existentes.
- Coliseu, recordes e runs/desafios Soulslike.
- Santuários em threads, cargos/verificação e progressão/Sentinela.
- Notificações de YouTube, jogos gratuitos/promoções e Nexus AI (Gemini).
- Banco principal com usuários, platinas, runs, provas, jogos zerados, perfis, inventário e registros de eventos.

O ZIP original continha código e testes, não um banco de produção para migrar. Portanto, não foi possível conferir o conteúdo de dados reais ou validar integridade de bancos de implantação.

### Catálogo

O catálogo original concentra boa parte da interface/comandos em `bot.py` e possui inicialização própria. O código inclui:

- Catálogo de jogos com busca, filtros, paginação, capas/imagens, links e tutorial/ISO quando fornecidos.
- Catálogo de mods e seus próprios fluxos de administração.
- Envio de conteúdo por membros, pendências e aprovação/rejeição.
- Mensagens/painéis com identificadores persistidos.
- Integração de notícias/feed RSS.
- Banco `jogos.db` com catálogo de jogos, mods e configurações próprias.

O ZIP do catálogo também não continha `jogos.db` nem as pastas de dados/imagens de produção. Esses elementos precisam ser copiados da hospedagem antiga antes de trocar a instalação.

## 2. Decisões de arquitetura

1. **Um único cliente autenticado:** `bot.py` passa a ser o ponto de entrada e carrega o catálogo como extensão na árvore de comandos principal. Não é necessário executar o antigo bot de catálogo separadamente.
2. **Bancos mantidos separados:** o banco principal preserva o esquema Soulsbot e recebe as tabelas de configurações, auditoria e clãs. `jogos.db` continua isolado para proteger o esquema do catálogo e os caminhos/imagens preexistentes. O banco de notificações de ofertas segue no diretório de dados.
3. **Configuração por `guild_id`:** associações de canais, cargos, categorias e módulos são persistidas e isoladas por servidor. O sistema importa IDs antigos do ambiente apenas quando o recurso existe no servidor e a chave ainda não foi configurada; não sobrescreve configurações salvas pelo painel.
4. **Migrações não destrutivas:** o schema usa `CREATE TABLE IF NOT EXISTS`, índices e trigger. Não há uma fusão automática de bancos nem exclusão automática de dados antigos.
5. **Permissões revalidadas:** `/adm` exige permissão nativa de Gerenciar Servidor/Administrador ou cargo administrativo configurado, rechecado em cada interação. O gerenciamento de clãs usa transações SQLite independentes para reduzir a chance de uma transação de clã ser confirmada inadvertidamente por outro módulo.

## 3. Implementado nesta entrega

- Inicialização centralizada e carregamento de extensões dos dois projetos.
- Comandos do catálogo registrados no cliente principal e mantendo o banco próprio.
- Camada central `settings_store.py`, persistência de configurações e trilha de auditoria.
- Associações administrativas para destinos de canais, categorias e cargos por seletores do Discord.
- Migração inicial de IDs antigos válidos, sem substituir valores mais recentes do painel.
- `/adm` efêmero e paginado com visão geral, configuração, organização, módulos, catálogo, YouTube/ofertas, progressão, clãs, diagnóstico, histórico, backup e ajuda.
- Organizador com prévia/confirmacão que cria apenas categorias/canais ausentes; não renomeia, move ou exclui recursos existentes.
- Geração de backup ZIP com snapshots SQLite dos bancos existentes nos caminhos configurados, além de snapshot pré-migração automático do banco principal quando uma versão de schema mais recente será aplicada.
- Sistema de clãs com exclusividade por usuário/servidor, regra de no máximo dez integrantes, convites, candidaturas, funções internas, transferências/encerramento com confirmação, atividades, estatísticas básicas, categorias/canais privados, auditoria, diagnóstico e tentativa de reparo.
- Configuração do destino do painel público “Salão dos Juramentos” e modo de recrutamento padrão.
- Configuração central aplicada aos destinos mais comuns de YouTube, promoções/ofertas, aprovações de platina e runs, Coliseu, santuários e zerados.
- `.env` de exemplo limpo, dependências atualizadas e guia de implantação.
- Limpeza de arquivos vazios/duplicados que vieram no ZIP original.

## 4. Garantias e limites importantes

### Sistema de clãs

- A exclusividade é apoiada por chave primária de membro e restrição de criador no banco.
- Um trigger SQLite aborta a inclusão de um 11º integrante, inclusive em concorrência entre conexões.
- Convites/candidaturas pendentes possuem índices únicos para reduzir duplicidade.
- Canais e categoria são configurados com `@everyone` sem acesso; líder, bot, integrantes e cargos de equipe explicitamente autorizados recebem permissões. Entradas/saídas atualizam permissões e há ferramenta administrativa para tentar reparar recursos ausentes.
- Administradores e pessoas com permissões suficientes do servidor ainda podem conseguir acessar canais privados. Não existe promessa de privacidade absoluta contra quem controla as permissões do servidor.
- **A progressão competitiva de clãs não concede XP ou recompensas automáticas.** Não foram definidos parâmetros definitivos de pontuação/recompensa. O ranking é básico/provisório, com base em atividades que constem como concluídas e tamanho. A UI para marcar atividade como concluída ainda não foi implementada, então a parte de ranking por conclusão não está pronta para competição real.
- Ainda não existe política automática completa de sucessão quando o líder sai do servidor, nem cooldown configurável de troca de clã. O histórico permanece registrado para recuperação/auditoria.

### Administração e organização do servidor

- O organizador **não** modifica nomes, movimenta, consolida ou exclui canais/cargos existentes. Ele cria recursos ausentes apenas. Isso reduz risco de perda de histórico e referências quebradas, mas não satisfaz integralmente uma reconstrução destrutiva e automatizada da estrutura.
- Algumas opções de liga/desliga na tela `/adm` são informativas e ainda não desconectam todos os listeners/tarefas daquele módulo. O toggle funcional implementado é o de novas interações do Sistema de Clãs.
- O painel cria backups, mas **não possui uma UI de restauração**. A restauração deve ser feita com o processo parado, preservando primeiro cópia do estado atual.
- Diagnóstico informa problemas e oferece reparo de recursos dos clãs; não é um reparo automático universal de todos os módulos.
- Tokens e chaves externas continuam dependendo de `.env`/hospedagem. Não é seguro mover credenciais para mensagens do Discord.

### Dados ausentes

Nenhum dos dois ZIPs incluía o banco principal, `jogos.db`, imagens, capas ou banco de ofertas da instalação de produção. O código mantém a compatibilidade de caminhos, mas os dados reais não podem ser inventados/reconstruídos. Faça cópia desses arquivos do ambiente antigo antes de implantar.

## 5. Testes executados

| Verificação | Resultado |
|---|---|
| `python -m compileall -q bot.py config.py database.py settings_store.py cogs tests` | Passou |
| `python -m unittest discover -s tests -v` | 32 testes passaram |
| Isolamento das configurações por servidor | Coberto por teste unitário |
| Migração versionada, adição de coluna legada e snapshot pré-migração | Coberto por teste unitário |
| Limite máximo de dez integrantes / exclusividade de vínculo | Coberto por teste de SQLite e trigger |
| Login no Discord, sincronização de slash commands e interações reais | **Não executado** |

As dependências `discord.py`, `aiosqlite` e `google-genai` não estavam instaladas no ambiente disponível, e o ambiente não conseguiu instalá-las por ausência de conectividade de pacote. Assim, compile/teste offline não equivalem a validar importação e execução real da aplicação com a API do Discord. O bot necessita de instalação das dependências e um teste em servidor isolado antes de produção.

## 6. Roteiro recomendado de implantação

1. Fazer backup e parar os dois processos antigos.
2. Copiar banco principal, `jogos.db`, banco de ofertas e pastas de capas/mods para os caminhos configurados.
3. Instalar as dependências e preencher segredos necessários no `.env`.
4. Habilitar intents de Members, Message Content e Voice States no Developer Portal quando aplicáveis.
5. Iniciar somente `python bot.py`; verificar todos os logs de carregamento de extensões.
6. Abrir `/adm`, configurar cargos administrativos, canais/categorias e confirmar a configuração migrada.
7. No servidor de teste, validar aprovações, catálogo, notícias, notificações, criação de clã, convite/candidatura, limite de integrantes, permissões efetivas, saída, transferência e encerramento.
8. Publicar o Salão dos Juramentos pelo `/adm` → Sistema de Clãs apenas após conferir a privacidade das categorias.
9. Manter cópias externas dos backups. Não considerar rollback garantido para alterações feitas diretamente no servidor Discord.
