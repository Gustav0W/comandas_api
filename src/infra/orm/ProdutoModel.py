from src.infra import database
from sqlalchemy import Column, VARCHAR, Integer, Float, LargeBinary

class ProdutoDB(database.Base):
    __tablename__ = 'tb_produto'

    id_produto = Column(Integer, primary_key=True, autoincrement=True, index=True)
    nome = Column(VARCHAR(100), nullable=False)
    preco = Column(Float, nullable=False)
    foto = Column(LargeBinary, nullable=True)
    descricao = Column(VARCHAR(255), nullable=True)

    def __init__(self, id_produto, nome, preco, foto, descricao=None):
        self.id_produto = id_produto
        self.nome = nome
        self.preco = preco
        self.foto = foto
        self.descricao = descricao
