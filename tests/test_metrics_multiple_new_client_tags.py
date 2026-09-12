from sqlalchemy import create_engine, MetaData, Table, Column, String, Boolean, literal, update
from app.modules.metrics.infrastructure.repository import new_clients_statement
from app.modules.transactions.domain.models import Transaction, TransactionTag, Tag
from app.modules.coin.domain.models import TaxRate


def test_multiple_new_client_tags_count_transactions_once():
    """Execute the panel's actual aggregation with overlapping tag assignments."""
    engine = create_engine('sqlite:///:memory:')
    metadata = MetaData()
    def table(model, *columns):
        return Table(model.__tablename__, metadata, *columns, schema=model.__table__.schema)
    rates = table(TaxRate, Column('id', String, primary_key=True))
    transactions = table(Transaction, Column('id', String, primary_key=True), Column('tax_rate_id', String))
    tags = table(Tag, Column('id', String, primary_key=True), Column('deleted', Boolean), Column('counts_as_new_client', Boolean))
    links = table(TransactionTag, Column('transaction_id', String), Column('tag_id', String), Column('deleted', Boolean))
    with engine.begin() as connection:
        for schema in {t.schema for t in metadata.tables.values()}:
            connection.exec_driver_sql(f'ATTACH DATABASE ":memory:" AS "{schema}"')
        metadata.create_all(connection)
        connection.execute(rates.insert(), [{'id': 'rate'}])
        connection.execute(transactions.insert(), [{'id': i, 'tax_rate_id': 'rate'} for i in ['one', 'two', 'three', 'four']])
        connection.execute(tags.insert(), [
            {'id': 'a', 'deleted': False, 'counts_as_new_client': True},
            {'id': 'b', 'deleted': False, 'counts_as_new_client': True},
            {'id': 'other', 'deleted': False, 'counts_as_new_client': False},
            {'id': 'removed', 'deleted': True, 'counts_as_new_client': True},
        ])
        connection.execute(links.insert(), [
            {'transaction_id': tx, 'tag_id': tag, 'deleted': False}
            for tx, tag in [('one', 'a'), ('two', 'b'), ('three', 'a'), ('three', 'b'), ('four', 'other'), ('four', 'removed')]
        ])
        statement = new_clients_statement(literal('period'), [])
        assert connection.execute(statement).one().clientes_nuevos == 3
        connection.execute(update(tags).where(tags.c.id == 'a').values(counts_as_new_client=False))
        assert connection.execute(statement).one().clientes_nuevos == 2
    engine.dispose()
