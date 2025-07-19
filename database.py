# database.py
# Contém a classe DatabaseManager para gerenciar todas as interações com o banco de dados SQLite.

import sqlite3

class DatabaseManager:
    """aqui a gente vai gerenciar nossa conexão com o diabo do banco de dados"""
    def __init__(self, db_file):
        self.db_file = db_file
        self.conn = None
        self.cursor = None

    def connect(self):
        self.conn = sqlite3.connect(self.db_file)
        self.conn.execute("PRAGMA foreign_keys = ON;") # pra garantir que as chaves estrangeiras funcionem
        self.cursor = self.conn.cursor()

    def close(self):
        if self.conn:
            self.conn.close()

    def execute_query(self, query, params=(), fetch=None):
        """se for preciso, executa uma query no banco de dados e retorna o resultado"""
        self.cursor.execute(query, params)
        if fetch == 'one':
            return self.cursor.fetchone() # retorna 1 resultado só 
        if fetch == 'all':
            return self.cursor.fetchall() # retorna todos 
        self.conn.commit() 
        return self.cursor.lastrowid # i aqui a gente retorna o id do ultimo registro inserido

    def create_tables(self):
        queries = [
            """
            CREATE TABLE IF NOT EXISTS fornecedores (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nome TEXT NOT NULL,
                empresa TEXT,
                telefone TEXT,
                email TEXT,
                morada TEXT
            );
            """,
            """
            CREATE TABLE IF NOT EXISTS localizacoes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nome TEXT NOT NULL UNIQUE,
                endereco TEXT
            );
            """,
            """
            CREATE TABLE IF NOT EXISTS produtos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nome TEXT NOT NULL,
                descricao TEXT,
                categoria TEXT,
                codigo_barras TEXT,
                preco_compra REAL NOT NULL,
                preco_venda REAL NOT NULL,
                ponto_ressuprimento INTEGER NOT NULL,
                fornecedor_id INTEGER NOT NULL,
                FOREIGN KEY (fornecedor_id) REFERENCES fornecedores (id) ON DELETE CASCADE
            );
            """,
            """
            CREATE TABLE IF NOT EXISTS estoque (
                produto_id INTEGER NOT NULL,
                localizacao_id INTEGER NOT NULL,
                quantidade INTEGER NOT NULL,
                PRIMARY KEY (produto_id, localizacao_id),
                FOREIGN KEY (produto_id) REFERENCES produtos (id) ON DELETE CASCADE,
                FOREIGN KEY (localizacao_id) REFERENCES localizacoes (id) ON DELETE CASCADE
            );
            """,
            """
            CREATE TABLE IF NOT EXISTS historico_movimentos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                produto_id INTEGER NOT NULL,
                localizacao_id INTEGER NOT NULL,
                tipo TEXT NOT NULL,
                quantidade INTEGER NOT NULL,
                data TEXT NOT NULL,
                FOREIGN KEY (produto_id) REFERENCES produtos (id) ON DELETE CASCADE,
                FOREIGN KEY (localizacao_id) REFERENCES localizacoes (id) ON DELETE CASCADE
            );
            """,
            """
            CREATE TABLE IF NOT EXISTS ordens_compra (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                fornecedor_id INTEGER NOT NULL,
                status TEXT NOT NULL,
                data_criacao TEXT NOT NULL,
                FOREIGN KEY (fornecedor_id) REFERENCES fornecedores(id) ON DELETE CASCADE
            );
            """,
            """
            CREATE TABLE IF NOT EXISTS itens_ordem_compra (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ordem_id INTEGER NOT NULL,
                produto_id INTEGER NOT NULL,
                quantidade INTEGER NOT NULL,
                preco_unitario REAL NOT NULL,
                FOREIGN KEY (ordem_id) REFERENCES ordens_compra(id) ON DELETE CASCADE,
                FOREIGN KEY (produto_id) REFERENCES produtos(id) ON DELETE CASCADE
            );
            """,
            """
            CREATE TABLE IF NOT EXISTS vendas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                cliente_nome TEXT NOT NULL,
                data TEXT NOT NULL
            );
            """,
            """
            CREATE TABLE IF NOT EXISTS itens_venda (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                venda_id INTEGER NOT NULL,
                produto_id INTEGER NOT NULL,
                quantidade INTEGER NOT NULL,
                preco_venda_unitario REAL NOT NULL,
                FOREIGN KEY (venda_id) REFERENCES vendas(id) ON DELETE CASCADE,
                FOREIGN KEY (produto_id) REFERENCES produtos(id) ON DELETE CASCADE
            );
            """
        ]
        for query in queries:
            self.execute_query(query)