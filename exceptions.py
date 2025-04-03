"""
Módulo para definições de exceções customizadas.
"""

class CalculationError(Exception):
    """Exceção levantada quando ocorre um erro durante um cálculo."""
    pass

class InputValidationError(Exception):
    """Exceção levantada quando os parâmetros de entrada são inválidos."""
    pass
