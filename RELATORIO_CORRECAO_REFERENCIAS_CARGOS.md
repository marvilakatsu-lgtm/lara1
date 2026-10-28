# Correção da prévia de limpeza — referências antigas de cargos

## Sintoma

A prévia bloqueava a limpeza por `role_bot_catalog_id` e `role_bot_soulsbot_id`, embora o projeto já tenha sido integrado em uma única aplicação de bot e os cargos `Bot Catálogo` e `Soulsbot` fossem candidatos à remoção.

## Causa

O validador tratava toda configuração `*_role_id` como referência ativa, sem distinguir as duas chaves legadas da arquitetura anterior. Isso impedia remover os cargos antigos mesmo que os módulos atuais não consumissem essas chaves.

## Correção

- Somente as chaves exatas `role_bot_catalog_id` e `role_bot_soulsbot_id`, quando apontam respectivamente para cargos chamados `Bot Catálogo` e `Soulsbot` que já estão na lista de exclusão, são classificadas como referências obsoletas.
- A prévia apresenta as chaves como migração que será realizada durante a limpeza confirmada.
- As chaves legadas são incluídas na assinatura do plano e no manifesto do backup.
- Depois de revalidar o plano, e somente após a confirmação explícita do dono, o sistema remove essas duas configurações com registro de auditoria antes de excluir os cargos.
- Qualquer outra referência ativa a um cargo excedente continua bloqueando a limpeza.
- Não há alteração durante a prévia.

## Validação local

- Compilação Python: aprovada.
- `python -m unittest discover -v`: 62 testes aprovados.
- O ambiente não tem `discord.py` instalado nem credenciais para executar a limpeza na guild real. A operação precisa ser validada no servidor, após gerar backup e revisar o manifesto.

## Observação de segurança

A limpeza é destrutiva. O backup contém bancos de dados e inventário de metadados, mas não restaura histórico de mensagens, threads nem anexos hospedados pelo Discord.
