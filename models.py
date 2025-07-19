# models.py
# Contém as definições de todas as classes de dados (dataclasses) da aplicação.

from dataclasses import dataclass, field
from datetime import datetime
from collections import defaultdict

#region Data Classes

@dataclass
class Fornecedor:
    """dados de contato de um fornecedor"""
    id: int
    nome: str
    empresa: str
    telefone: str
    email: str
    morada: str 

    def __str__(self):
        """isso vai ser usado para exibir o fornecedor em uma lista"""
        return f"{self.id} - {self.nome}"

@dataclass
class Localizacao:
    # repsresenta uma localização física no inventário, como um armazém ou uma loja mesmo
    id: int
    nome: str
    endereco: str = ""

    def __str__(self):
        #aquela mesma parada lá, de exibir a localização em uma lista
        return f"{self.id} - {self.nome}"

@dataclass
class Produto:
    """produto no inventário."""
    id: int
    nome: str
    descricao: str
    categoria: str
    fornecedor: Fornecedor
    codigo_barras: str
    preco_compra: float
    preco_venda: float
    ponto_ressuprimento: int # o ponto de ressuprimento é o estoque mínimo que deve ser mantido
    # aqui vamos usar um defaultdict para armazenar a quantidade do produto por nome de localização
    estoque_por_local: defaultdict[str, int] = field(default_factory=lambda: defaultdict(int))

    def get_estoque_total(self) -> int:
        """faz o calculo e retorna a soma do estoque de todas as localizações"""
        return sum(self.estoque_por_local.values())
        # socorro

@dataclass
class HistoricoMovimento:
    """aqui, nós registramos as movimentações de estoque de um produto"""
    produto: Produto
    tipo: str # exemplo: entrada, saída, transferência
    quantidade: int
    localizacao: Localizacao
    data: datetime = field(default_factory=datetime.now)

@dataclass
class ItemOrdemCompra:
    """nisso, nós vamos representar um item dentro de uma ordem de Compra"""
    # ou seja, um produto que está sendo comprado através do fornecedor
    produto: Produto
    quantidade: int
    preco_unitario: float

    @property
    def subtotal(self) -> float:
        """calculo do valro subtotal do item da ordem de compra"""
        return self.quantidade * self.preco_unitario

@dataclass
class OrdemCompra:
    """aqui, nós ja temoos a nossa tal ordem de compra kkkkk ai meu deus eu tô ficando louco"""
    id: int
    fornecedor: Fornecedor
    itens: list[ItemOrdemCompra]
    status: str # : pendente, recebida, cancelada
    data_criacao: datetime = field(default_factory=datetime.now)

    @property
    def valor_total(self) -> float:
        """calcolo do valor total da ordem de compra"""
        return sum(item.subtotal for item in self.itens)

@dataclass
class ItemVenda:
    produto: Produto
    quantidade: int
    preco_venda_unitario: float

    @property
    def subtotal(self) -> float:
        return self.quantidade * self.preco_venda_unitario

@dataclass
class Venda:
    id: int
    cliente: str
    itens: list[ItemVenda]
    data: datetime = field(default_factory=datetime.now)

    @property
    def valor_total(self) -> float:
        return sum(item.subtotal for item in self.itens)

#endregion