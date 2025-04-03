"""
Módulo utilitário com funções comuns utilizadas no projeto.
"""

def min_max(val: float, min_val: float, max_val: float) -> float:
    """Limita um valor dentro de um intervalo definido.

    Args:
        val (float): Valor a ser limitado.
        min_val (float): Valor mínimo permitido.
        max_val (float): Valor máximo permitido.

    Returns:
        float: Valor limitado.
    """
    return max(min(val, max_val), min_val)

def int_ceiling(val: float) -> int:
    """Arredonda um número para o menor inteiro maior ou igual ao valor.

    Args:
        val (float): Valor a ser arredondado.

    Returns:
        int: Valor arredondado.
    """
    return int(val - 0.9999) if val < 0 else int(val + 0.9999)

def secs(amount: float, interval: float = 600.0) -> int:
    """Converte uma quantidade em horas para segundos.

    Args:
        amount (float): Quantidade a ser convertida.
        interval (float, optional): Fator de conversão. Padrão é 600 segundos.

    Returns:
        int: Quantidade convertida para segundos.
    """
    return int(amount * interval + 0.5)
