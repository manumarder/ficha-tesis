"""
Diccionario de categorías para productos de Canasta Básica
Mapea nombres de productos (o palabras clave) a categorías

Para agregar nuevos productos:
1. Agregar el nombre exacto en CATEGORIAS_PRODUCTOS
2. O agregar palabras clave en PALABRAS_CLAVE_CATEGORIAS
"""
CATEGORIAS_PRODUCTOS = {
    # Mapeo directo: nombre exacto del producto -> categoría
    'Aceite de Girasol': 'Aceites y Grasas',
    'Aceite de Maíz': 'Aceites y Grasas',
    'Aceite de Oliva': 'Aceites y Grasas',
    'Aceite Girasol': 'Aceites y Grasas',
    'Aceite Maíz': 'Aceites y Grasas',
    'Manteca': 'Aceites y Grasas',
    'Margarina': 'Aceites y Grasas',
    
    'Leche Entera': 'Lácteos',
    'Leche Descremada': 'Lácteos',
    'Leche': 'Lácteos',
    'Yogur': 'Lácteos',
    'Queso': 'Lácteos',
    'Crema de Leche': 'Lácteos',
    'Dulce de Leche': 'Lácteos',
    'Manteca': 'Lácteos',
    
    'Pan': 'Panadería',
    'Galletas': 'Panadería',
    'Galletitas': 'Panadería',
    'Galletitas dulces': 'Panadería',
    'Facturas': 'Panadería',
    'Tostadas': 'Panadería',
    'Bizcochos': 'Panadería',
    
    'Azúcar': 'Almacén',
    'Harina': 'Almacén',
    'Fideos': 'Almacén',
    'Arroz': 'Almacén',
    'Sal': 'Almacén',
    'Aceitunas': 'Almacén',
    'Tomate en Lata': 'Almacén',
    'Tomate Triturado': 'Almacén',
    'Puré de Tomate': 'Almacén',
    
    'Carne': 'Carnes',
    'Pollo': 'Carnes',
    'Pescado': 'Carnes',
    'Jamón': 'Carnes',
    'Salchichas': 'Carnes',
    'Chorizo': 'Carnes',
    
    'Tomate': 'Frutas y Verduras',
    'Cebolla': 'Frutas y Verduras',
    'Papa': 'Frutas y Verduras',
    'Zanahoria': 'Frutas y Verduras',
    'Lechuga': 'Frutas y Verduras',
    'Manzana': 'Frutas y Verduras',
    'Banana': 'Frutas y Verduras',
    
    'Gaseosa': 'Bebidas',
    'Agua': 'Bebidas',
    'Jugo': 'Bebidas',
    'Bebida': 'Bebidas',
    
    'Detergente': 'Limpieza',
    'Jabón en Polvo': 'Limpieza',
    'Lavandina': 'Limpieza',
    'Limpiador': 'Limpieza',
    'Desinfectante': 'Limpieza',
    
    'Shampoo': 'Higiene Personal',
    'Jabón': 'Higiene Personal',
    'Pasta Dental': 'Higiene Personal',
    'Papel Higiénico': 'Higiene Personal',
    'Toallitas': 'Higiene Personal',
}

# Palabras clave para categorización automática (si no hay match exacto)
PALABRAS_CLAVE_CATEGORIAS = {
    'Aceites y Grasas': ['aceite', 'grasa', 'manteca', 'margarina'],
    'Lácteos': ['leche', 'yogur', 'queso', 'crema', 'dulce de leche'],
    'Panadería': ['pan', 'galleta', 'galletita', 'galletitas', 'factura', 'tostada', 'bizcocho', 'tartaleta'],
    'Carnes': ['carne', 'pollo', 'pescado', 'jamón', 'salchicha', 'chorizo'],
    'Frutas y Verduras': ['tomate', 'cebolla', 'papa', 'zanahoria', 'lechuga', 'manzana', 'banana'],
    'Bebidas': ['gaseosa', 'agua', 'jugo', 'bebida', 'refresco'],
    'Almacén': ['azúcar', 'harina', 'fideo', 'arroz', 'sal', 'aceituna', 'lata', 'conserva', 'puré'],
    'Limpieza': ['detergente', 'jabón en polvo', 'lavandina', 'limpiador', 'desinfectante'],
    'Higiene Personal': ['shampoo', 'jabón', 'pasta dental', 'papel higiénico', 'toallitas'],
}


def obtener_categoria(producto_nombre: str) -> str:
    """
    Obtiene la categoría de un producto basándose en el diccionario
    
    Args:
        producto_nombre: Nombre del producto a categorizar
    
    Returns:
        str: Nombre de la categoría o "Sin Categoría" si no se encuentra
    
    Ejemplo:
        >>> obtener_categoria("Aceite de Girasol")
        'Aceites y Grasas'
        >>> obtener_categoria("Leche Entera 1L")
        'Lácteos'
    """
    if not producto_nombre:
        return "Sin Categoría"
    
    producto_lower = str(producto_nombre).lower().strip()
    
    # 1. Buscar match exacto (case insensitive)
    for producto, categoria in CATEGORIAS_PRODUCTOS.items():
        if producto.lower() == producto_lower:
            return categoria
    
    # 2. Buscar por palabras clave
    for categoria, palabras_clave in PALABRAS_CLAVE_CATEGORIAS.items():
        for palabra in palabras_clave:
            if palabra.lower() in producto_lower:
                return categoria
    
    # 3. Si no encuentra, retornar "Sin Categoría"
    return "Sin Categoría"

