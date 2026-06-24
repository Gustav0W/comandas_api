from sqlalchemy import Column, DateTime, DECIMAL, ForeignKey, Integer

from infra.database import Base


class RecebimentoDB(Base):
    __tablename__ = "tb_recebimento"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    data_hora = Column(DateTime, nullable=False)
    funcionario_id = Column(
        Integer, ForeignKey("tb_funcionario.id", ondelete="RESTRICT"), nullable=False
    )
    desconto = Column(DECIMAL(10, 2), nullable=False, default=0)
    acrescimo = Column(DECIMAL(10, 2), nullable=False, default=0)
    valor_subtotal = Column(DECIMAL(10, 2), nullable=False)
    valor_total = Column(DECIMAL(10, 2), nullable=False)
    cliente_id = Column(
        Integer,
        ForeignKey("tb_cliente.id_cliente", ondelete="RESTRICT"),
        nullable=True,
        default=None,
    )


class RecebimentoComandaDB(Base):
    __tablename__ = "tb_recebimento_comanda"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    recebimento_id = Column(
        Integer, ForeignKey("tb_recebimento.id", ondelete="CASCADE"), nullable=False
    )
    comanda_id = Column(
        Integer, ForeignKey("tb_comanda.id", ondelete="RESTRICT"), nullable=False
    )
