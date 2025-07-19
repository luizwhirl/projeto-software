# config.py
# Contém as variáveis de configuração e constantes do projeto.

import os

# a reportlab serve pra gerar relatórios em PDF
try:
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.units import inch
    REPORTLAB_DISPONIVEL = True
except ImportError:
    REPORTLAB_DISPONIVEL = False
    
DB_FILE = "estoque_database.db"