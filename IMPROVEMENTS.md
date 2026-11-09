# Interface e desempenho

## Interface

- Visual compartilhado entre login, contagem e administração.
- Contagem em cartões no celular, sem rolagem horizontal.
- Busca por nome ou código, ignorando acentos, sem chamadas ao servidor.
- Indicador de produtos preenchidos e botão de envio acessível durante a rolagem.
- Rótulos nos campos, navegação por teclado e respeito à preferência de movimento reduzido.
- Relatório com cabeçalho e nomes dos produtos fixos durante a rolagem.
- Botões de formulário recuperados ao voltar pelo histórico; confirmações canceladas não bloqueiam o formulário.

## Desempenho e correções

- Relatório usa uma conexão por execução, em vez de três.
- Quantidades agregadas com SUM/GROUP BY no banco, sem DataFrames/pivots por requisição.
- pandas, NumPy e pyodbc deixam de ser importados pelo servidor web. As dependências foram mantidas para os scripts de sincronização.
- Biblioteca de PDF carregada apenas na exportação.
- Envio de contagem com executemany e validação antes de substituir os dados existentes.
- CSS/JavaScript compartilhados em arquivos estáticos com cache de uma hora.
- migrate_render.py cria índices idempotentes para pedidos por data/loja e disponibilidade por dia.
- Salvar pedido usa a data selecionada no relatório.
- Datas inválidas são normalizadas e as consultas usam parâmetros.
- Dias desativados são respeitados nos relatórios; dias adicionais ativos não causam erro de nome.
- Nomes dos dias corrigidos na lista de produtos.

## Validação

Antes de publicar em produção, configure SECRET_KEY com um valor aleatório longo e persistente no ambiente do servidor. A chave fixa que estava no código foi removida. Com DATABASE_URL configurada, a aplicação exige SECRET_KEY para iniciar; isso mantém a mesma chave entre reinicializações e workers. No desenvolvimento sem banco remoto, uma chave temporária é gerada a cada início.

Execute, com as dependências instaladas:

```sh
python -m unittest discover -s tests -v
node --check static/app.js
git diff --check
```

11 testes cobrem totais, datas, autorização, envio/validação de contagens, PDF, páginas administrativas e repetição da migração sem perda de dados. O teste de conexão verifica o uso de apenas uma conexão no relatório. EXPLAIN QUERY PLAN confirma o índice de data/loja no SQLite.

Verificação adicional no Edge headless com dados fictícios: desktop de 1440 px, celular de 390 px, busca sem acento, estado vazio, progresso, envio e recuperação de valores, salvar na data escolhida, download de PDF e estilos de impressão. Nenhum erro de JavaScript foi observado. Como o ambiente restringe conexões HTTP locais, as requisições da aplicação foram atendidas pelo cliente de teste Flask durante essa verificação.

PostgreSQL e o serviço de produção não foram exercitados. Não há medição de latência de produção nem promessa de ganho percentual. A migração usa CREATE INDEX convencional; programe a publicação conforme o volume das tabelas, pois a criação inicial pode bloquear escritas temporariamente.
