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
- Organizador com prévia/confirmacão para a estrutura específica Quase Pro: 8 categorias, 28 canais e 31 cargos. Reutiliza canais por nome/alias, renomeia e move para a nova ordem, padroniza cores/permissões dos cargos e normaliza a privacidade das categorias; não exclui canais ou mensagens.
- Painel persistente de verificação em `✅・verificação`, painel de escolha de cargos, painéis de catálogo de jogos/mods e Salão dos Juramentos, reutilizados por ID ou custom_id para reduzir duplicatas.
- Sincronização do cargo de patente pelo XP/nível atual e publicação do painel de self-roles para 6 jogos e 3 avisos/eventos.
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

- O organizador renomeia e move canais que correspondem por nome/alias e atualiza overwrites das 8 categorias. A categoria `👋・INÍCIO` permanece pública e somente leitura para não verificados; as outras seis categorias públicas negam `view_channel` a `@everyone` e concedem visibilidade ao cargo `🟢・Membro` após verificação. A categoria da equipe mantém ACL restrita. Não exclui canais, mensagens ou bancos. A alteração de permissões/categorias no Discord não possui rollback automático garantido, logo deve ser testada num servidor de homologação e pode falhar parcialmente se houver rate limits, permissões insuficientes ou hierarquia inadequada.
- O plano cria/atualiza 31 cargos funcionais com paleta única. Cargos administrativos preexistentes configurados continuam associados para evitar bloquear a equipe; os cargos oficiais de comunidade/notificações passam para as definições padronizadas.
- Como Soulsbot, catálogo e organizador estão carregados num único cliente Discord, as três antigas etiquetas decorativas de bot não são mais criadas. Se já existirem no servidor, não são removidas automaticamente para evitar apagar atribuições ou overwrites existentes.
- Algumas opções de liga/desliga na tela `/adm` são informativas e ainda não desconectam todos os listeners/tarefas daquele módulo. O toggle funcional implementado é o de novas interações do Sistema de Clãs.
- O painel cria backups, mas **não possui uma UI de restauração**. A restauração deve ser feita com o processo parado, preservando primeiro cópia do estado atual.
- Diagnóstico informa problemas e oferece reparo de recursos dos clãs; não é um reparo automático universal de todos os módulos.
- Tokens e chaves externas continuam dependendo de `.env`/hospedagem. Não é seguro mover credenciais para mensagens do Discord.

### Dados ausentes

Nenhum dos dois ZIPs incluía o banco principal, `jogos.db`, imagens, capas ou banco de ofertas da instalação de produção. O código mantém a compatibilidade de caminhos, mas os dados reais não podem ser inventados/reconstruídos. Faça cópia desses arquivos do ambiente antigo antes de implantar.

## 4.1. Revisão de usabilidade — estrutura comunitária simplificada (28/10/2026)

- A navegação foi reduzida de 10 para 8 categorias e de 63 para 28 canais planejados (incluindo a área privada da equipe). Os canais de entrada são somente leitura para `@everyone`; a verificação continua disponível por botão.
- Destinos combinados: avisos/vídeos; jogos/mods/envio de mods; ofertas/notícias/jogos grátis; perfis/platinas/zerados; Coliseu/runs; Salão dos Juramentos/recrutamento/ranking/eventos.
- Canais antigos redundantes são movidos para `🗄️・ARQUIVO ANTIGO` com acesso restrito à equipe; categorias antigas conhecidas são ocultadas. Não há exclusão automática de mensagens ou canais.
- Os IDs de configuração dos módulos continuam preservados, ainda que apontem ao mesmo canal. Isso permite consolidar a navegação sem quebrar as automações que consultam chaves distintas.
- As três etiquetas decorativas de bot deixaram de ser parte dos cargos gerenciados, pois a integração utiliza uma única identidade Discord. Patentes, cargos de equipe, comunidade, clã e interesses mantêm seus nomes/cores e o XP segue os limiares originais.

## 5. Testes executados

| Verificação | Resultado |
|---|---|
| `python -m compileall -q bot.py config.py database.py settings_store.py cogs tests` | Passou |
| `python -m unittest discover -s tests -v` | 58 testes passaram na versão atual com limpeza destrutiva opcional |
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

## Correções pós-entrega e versão da estrutura

O fluxo de `/adm` não passa `None` a `guild.create_category(overwrites=...)`: categorias regulares recebem `{}`, e a categoria da equipe recebe seu mapa de permissões específico. O callback de confirmação registra falhas inesperadas e responde ao administrador de forma efêmera. A ordem dos campos da estrutura foi alinhada às rotinas de prévia/aplicação, e um teste impede regressão do schema. O catálogo publica nos canais configurados e o organizador cria/atualiza os painéis persistentes. Testes locais na versão atual: 49 aprovados; a execução end-to-end com Discord permanece pendente de credenciais e instalação das dependências na hospedagem.

## Adendo — erro de anexo do catálogo e fallback de YouTube (28/10/2026)

**Erro observado no Discord:** `AttributeError: 'NoneType' object has no attribute 'to_dict'` em `MainView.ver`, quando `CatalogView.render()` retorna um embed e `file=None`. O mesmo padrão existia no fluxo de busca por jogo.

**Correção:** ambos os callbacks agora passam os argumentos por `send_kwargs`, que inclui `file` somente se houver um objeto de anexo. A grade e a ficha continuam sendo enviadas mesmo sem uma imagem local disponível.

**Aviso separado:** `Feed RSS do YouTube ... HTTP 404` não é a causa do traceback do catálogo. O feed falho faz o módulo tentar a API, quando possível. A mensagem agora reconhece duas hipóteses que não podem ser diferenciadas apenas pelo status 404: indisponibilidade temporária do endpoint ou ID incorreto. Os avisos repetidos são limitados a uma ocorrência por 15 minutos; a API ainda pode ser consultada no intervalo configurado do loop.

**Testes realizados antes da correção de hierarquia:** compilação de todos os módulos e 43 testes unitários aprovados, incluindo um teste de regressão que impede novos `send_message(file=file)` diretos no código do catálogo. Não houve teste autenticado contra o Discord ou YouTube nesta execução.

## Adendo — hierarquia de cargos (28/10/2026)

- A ordenação anterior seguia a lista de criação das patentes, o que deixava a patente inicial acima das mais altas. Agora a pilha é calculada por `level_min` em ordem decrescente: Sentinela Imortal → Lenda do Coliseu → Senhor das Almas → Executor Sombrio → Arauto da Ruína → Guardião das Cinzas → Cavaleiro do Abismo → Caçador de Almas → Guerreiro Caído → Cinzas Novatas.
- Líder de Clã > Oficial de Clã > Membro de Clã; Criador/Aliado > Membro > Recém-chegado; os nove cargos de interesse/notificação ficam na base.
- O organizador não tenta mais mover cargos de equipe para cima do próprio cargo do bot. Cargos funcionais são ordenados apenas abaixo do cargo real do bot. A ordem de equipe esperada é Fundador > Administrador > Moderador > Suporte > Desenvolvedor, acima do cargo do bot.
- A API do Discord impede um bot de ordenar ou editar cargos no mesmo nível ou acima da sua maior role. Por isso, quando os cargos de equipe recém-criados ainda estiverem abaixo do bot, o `/adm` informa que o administrador precisa movê-los manualmente em **Configurações do servidor → Cargos** e não deve atribuí-los a membros antes de concluir o ajuste. Após mover os cargos, executar `/adm` novamente valida a ordem. O diagnóstico também detecta cargos funcionais acima do bot ou fora da sequência.
- O mapeamento de IDs de cargos é persistido inclusive quando um cargo acima do bot não pode ser editado, evitando perder a associação ao reabrir o painel.
- Foram adicionados quatro testes da ordem da equipe, patentes descendentes, papéis de clã/comunidade e exclusão dos cargos de equipe da ordenação automática. Validação na etapa de hierarquia: `compileall` e 47 testes aprovados; a versão comunitária atual tem 49 testes aprovados. Não houve teste autenticado no Discord.


## Atualização posterior — limpeza destrutiva opcional (28/10/2026)

A versão atual adiciona uma ação separada em `/adm` para inventariar e, após confirmação do dono do servidor, excluir canais/categorias/cargos fora da estrutura oficial. A aplicação normal continua sem apagar. A ação destrutiva exige que os 8 grupos e os 28 canais-alvo existam, bloqueia referências persistentes não resolvidas, preserva clãs ativos/degradados, cargos gerenciados e cargos utilizados pelo bot, produz um pacote com snapshots de bancos e metadados e exige a frase `APAGAR RESTO`. O backup não consegue restaurar histórico de mensagens, threads ou anexos do Discord.

Validação atual: compilação Python aprovada e 58 testes passaram. Como o ambiente não possui `discord.py` nem credenciais da guild, o fluxo de exclusão não foi testado contra a API real; faça a primeira execução num servidor de homologação.
