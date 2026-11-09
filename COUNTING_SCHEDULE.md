# Contagens a partir de 09/11/2026

Listas conferidas a partir das duas fotos fornecidas pelo responsável:

- Terça-feira: 35 produtos marcados em verde.
- Quarta-feira: 36 produtos com asterisco.
- Sábado: os 99 produtos.
- Segunda, quinta, sexta e domingo: desativados.
- Maçã Pink substitui o nome Maçã Gala/Fuji da lista, código 310140.

counting_schedule.json contém a relação exata de códigos, nomes e dias. Os cinco produtos presentes em terça e quarta são batata lavada extra, cebola nacional, laranja-pera, moranga híbrida e tomate extra.

O comando de produção existente, gunicorn app:app, carrega gunicorn.conf.py. O hook on_starting executa schedule_update.py antes de iniciar os workers. A transação registra a aplicação dessa revisão, atualiza os vínculos dos três dias e o estado dos sete dias. Repetir o deploy não reaplica a revisão nem sobrescreve alterações administrativas posteriores.

Os produtos são encontrados pelo código, mantendo IDs, custos e unidades fracionadas existentes. Pêssego importado é reaproveitado do código antigo 310159 para o código 340137 da folha. Produtos ausentes são criados com custo zero até o cadastro/sincronização do custo. Nenhuma contagem, pedido final ou usuário é apagado.

Antes de atualizar, são guardados os vínculos, nomes, unidades, custos e estados dos dias. Relatórios de datas anteriores a 09/11/2026 usam esse histórico; relatórios a partir dessa data usam o cadastro atual. Os dados enviados anteriormente continuam com seus nomes originais.

Para desenvolvimento com flask run, execute antes python schedule_update.py no banco local inicializado. python app.py e o Gunicorn executam a atualização automaticamente.

Validação: python -m unittest discover -s tests -v. Os testes cobrem as três quantidades, dias inativos, relatórios históricos, preservação de IDs/custos/usuários/pedidos, reaplicação e rollback integral em caso de erro.
