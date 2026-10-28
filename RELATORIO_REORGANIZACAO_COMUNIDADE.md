# Reorganização comunitária do Quase Pro

**Versão:** estrutura comunitária simplificada — 28 de outubro de 2026

## Resultado

A estrutura de navegação foi reduzida de 10 para **8 categorias** e de 63 para **28 canais planejados**, incluindo a categoria privada da equipe. Os sistemas continuam disponíveis; a mudança concentra interfaces e destinos semelhantes, em vez de publicar um canal para cada comando ou subsistema.

## Estrutura final

| Categoria | Canais | Finalidade |
|---|---:|---|
| `👋・INÍCIO` | 3 | Boas-vindas, regras e verificação |
| `📣・QUASE PRO` | 3 | Avisos/vídeos, lives, conteúdo e votações |
| `💬・COMUNIDADE` | 6 | Conversa, memes/clipes, procurar jogadores, outros jogos, ajuda/sugestões e escolha de cargos |
| `🎮・SOULSLIKE` | 5 | Elden Ring, Dark Souls, outros Soulslikes, builds/chefes e runs/desafios |
| `📚・CATÁLOGO` | 2 | Jogos/mods/envio de mods; ofertas/notícias/jogos grátis |
| `🏆・PROGRESSÃO E CLÃS` | 3 | Perfis/conquistas, Coliseu/desafios e painel de clãs |
| `🔊・VOZ` | 3 | Papo livre, coop/jogos e eventos |
| `🔒・EQUIPE` | 3 | Chat da equipe, logs/auditoria e suporte/aprovações |

## Cargos

O plano gerencia **31 cargos funcionais com cores únicas**. Isso preserva os cargos solicitados e evita criar rótulos decorativos que fingem ser bots separados, embora toda a solução integrada use uma única identidade de bot no Discord.

| Grupo | Quantidade | Função |
|---|---:|---|
| Equipe | 5 | Fundador, Administrador, Moderador, Suporte, Desenvolvedor |
| Patentes Soulslike | 10 | Patentes preservadas com níveis mínimos 1, 5, 10, 15, 20, 30, 40, 50, 75 e 100 |
| Clãs | 3 | Líder, Oficial, Membro de Clã |
| Comunidade | 4 | Criador de Conteúdo, Aliado, Membro, Recém-chegado |
| Interesse e notificações | 9 | Seis jogos e três tipos de avisos |

A equipe fica acima do cargo real do bot. O bot ordena os cargos funcionais abaixo de si, mas não pode mover por API sua própria função acima do cargo mais alto. Essa parte exige uma única correção manual em **Configurações do servidor → Cargos**.

## Consolidações aplicadas

- Avisos e vídeos do canal compartilham `📣・avisos-e-vídeos`; lives permanecem separadas.
- Jogos, mods e submissões usam `📚・jogos-e-mods`, com painéis distintos no mesmo canal.
- Jogos grátis, promoções e notícias compartilham `🎁・ofertas-e-notícias`.
- Perfis, platinas, jogos zerados e conquistas compartilham `🏅・perfis-e-conquistas`.
- Coliseu, runs e desafios usam `⚔️・coliseu-e-desafios`.
- Descoberta, recrutamento, ranking e eventos de clãs são acessados pelo painel `🛡️・clãs`; as categorias privadas de cada clã continuam separadas.
- Help, IA e suporte de comunidade apontam para `💭・ajuda-e-sugestões`; a equipe e as aprovações internas continuam privadas.
- Os IDs de configuração antigos são mantidos como chaves separadas que podem apontar ao mesmo canal, para não quebrar os módulos existentes.

## Verificação e privacidade

`👋・INÍCIO` é visível aos recém-chegados, mas somente leitura para `@everyone`. O botão `Verificar-me` em `✅・verificação` atribui `🟢・Membro` e retira `🌱・Recém-chegado`. As outras seis categorias de uso comunitário exigem o cargo de membro verificado. `🔒・EQUIPE` e o arquivo antigo têm acesso restrito.

Ao aplicar a reorganização, o bot reutiliza, renomeia e move canais correspondentes por nome/aliases. Canais redundantes reconhecidos são movidos para `🗄️・ARQUIVO ANTIGO`, e categorias legadas conhecidas são ocultadas. **A migração não apaga mensagens, canais, cargos ou bancos.** Ainda assim, permissões e posições são alterações reais no Discord; a primeira aplicação deve ser conferida num servidor de teste.

## Validação executada

- `python -m compileall -q bot.py config.py database.py settings_store.py cogs tests server_structure.py levels.py`: **passou**.
- `python -m unittest discover -s tests -v`: **49 testes passaram**.
- Teste de estrutura: 8 categorias, 28 canais, 31 cargos com nomes/cores únicos.
- Teste de regressão: categorias de entrada permitem leitura aos não verificados, mas bloqueiam envio de mensagens e criação de threads.

**Limite importante:** não houve login real na API do Discord nesta sessão; as bibliotecas de runtime não estavam disponíveis neste ambiente. O resultado foi validado por compilação e testes locais, mas a criação/movimentação das categorias, a hierarquia real dos cargos e os painéis devem ser confirmados na hospedagem.

## Implantação sugerida

1. Faça backup do banco principal, `jogos.db`, banco de ofertas e pastas de capas/mods.
2. Atualize o código na hospedagem sem sobrescrever `.env` ou dados de produção.
3. Inicie apenas `python bot.py`.
4. Ajuste manualmente os cinco cargos de equipe acima do cargo do bot; mantenha o bot acima dos cargos funcionais.
5. Abra `/adm` → **Organização do servidor**, revise a prévia e confirme.
6. Teste verificação com uma conta nova, permissões de equipe, painéis de jogos/mods, notificações e fluxo de clãs antes de usar em produção.
