
# -*- coding: utf-8 -*-
import json
import unicodedata
import difflib
import heapq
import re
from typing import Dict, List, Tuple, Optional, Set

# ====== Clases base ======
class estacion:
    def __init__(self, nombre, sig_estacion, distancia_sig, ant_estacion, distancia_ant):
        self.nombre = nombre
        self.sig_estacion = sig_estacion
        self.distancia_sig = distancia_sig
        self.ant_estacion = ant_estacion
        self.distancia_ant = distancia_ant
        # lista de tuplas (linea_destino, nombre_estacion_destino)
        self.transbordos = []

class linea:
    def __init__(self, nombre, costo_transbordo_linea: Optional[int] = None):
        self.nombre = nombre
        self.estaciones: List[estacion] = []
        self.costo_transbordo_linea = costo_transbordo_linea  # opcional, si el JSON lo trae

    def agregar_estacion(self, estacion_obj):
        self.estaciones.append(estacion_obj)

class mapa_metro:
    def __init__(self, costo_transbordo_global: int = 250):
        self.lineas: List[linea] = []
        self.costo_transbordo_global = costo_transbordo_global

    def agregar_linea(self, linea_obj: linea):
        self.lineas.append(linea_obj)

# ====== Utilidades ======
def normaliza(s: str) -> str:
    s = s.strip().lower()
    s = ''.join(c for c in unicodedata.normalize('NFD', s) if unicodedata.category(c) != 'Mn')
    return s

SINONIMOS = {
    "salto de agua": "salto del agua",
    "tasqueña": "tasquena",
    "isabel la católica": "isabel la catolica",
    "zocalo/tecno": "zocalo",
    "cuatros caminos": "cuatro caminos",
}

def aplica_sinonimos(s: str) -> str:
    s_norm = normaliza(s)
    return SINONIMOS.get(s_norm, s_norm)

# ====== Persistencia: cargar JSON ======
def cargar_conocimiento_desde_archivo(ruta_json: str) -> Dict:
    with open(ruta_json, "r", encoding="utf-8") as f:
        data = json.load(f)
    if "lineas" not in data:
        raise ValueError("El JSON no contiene la clave 'lineas'.")
    return data

# ====== Construir mapa desde JSON (lee costos de transbordo) ======
def iniciar_mapa(ruta_json: str) -> mapa_metro:
    """
    Construye objeto mapa_metro desde el archivo JSON.
    Lee 'costo_transbordo' global (si existe) y opcionalmente uno por línea.
    Detecta transbordos entre estaciones con el mismo nombre normalizado en distintas líneas.
    """
    data = cargar_conocimiento_desde_archivo(ruta_json)

    # costo global
    costo_transbordo_global = int(data.get("costo_transbordo", 250))
    mapa = mapa_metro(costo_transbordo_global=costo_transbordo_global)

    estaciones_global: Dict[str, List[Tuple[str, estacion]]] = {}  # nombre_norm -> [(linea, est_obj)]
    lineas_json = data.get("lineas", {})

    for nombre_linea, info_linea in lineas_json.items():
        # opcional: costo por línea (si está en el JSON)
        costo_t_linea = info_linea.get("costo_transbordo", None)
        if costo_t_linea is not None:
            costo_t_linea = int(costo_t_linea)

        linea_obj = linea(nombre_linea, costo_transbordo_linea=costo_t_linea)
        estaciones_json = info_linea.get("estaciones", {})
        estaciones_lista = list(estaciones_json.items())  # preserva orden

        for i in range(len(estaciones_lista)):
            nombre_est, par_dist = estaciones_lista[i]
            dist_ant = par_dist[0] if par_dist and len(par_dist) > 0 else None
            dist_sig = par_dist[1] if par_dist and len(par_dist) > 1 else None

            # anterior
            ant = estaciones_lista[i-1][0] if i > 0 else None
            distA = dist_ant if i > 0 else None

            # siguiente
            sig = estaciones_lista[i+1][0] if i < len(estaciones_lista) - 1 else None
            distS = dist_sig if i < len(estaciones_lista) - 1 else None

            est_obj = estacion(nombre_est, sig, distS, ant, distA)
            linea_obj.agregar_estacion(est_obj)

            key = normaliza(nombre_est)
            estaciones_global.setdefault(key, []).append((nombre_linea, est_obj))

        mapa.agregar_linea(linea_obj)

    # Transbordos: mismo nombre normalizado entre líneas distintas
    for _, lista in estaciones_global.items():
        if len(lista) > 1:
            for i in range(len(lista)):
                li, est_i = lista[i]
                for j in range(len(lista)):
                    if i == j:
                        continue
                    lj, est_j = lista[j]
                    est_i.transbordos.append((lj, est_j.nombre))

    return mapa

# ====== Construir grafo desde 'mapa_metro' usando costo del JSON ======
def construir_grafo_desde_mapa(
    mapa: mapa_metro,
    costos_transbordo_por_estacion: Optional[Dict[str, int]] = None
) -> Dict[Tuple[str, str], List[Tuple[Tuple[str, str], int]]]:
    """
    Grafo: nodo es (linea, estacion_norm).
    Pesos:
      - Tramos (distancia_sig / distancia_ant).
      - Transbordos: prioriza costo por estación (si existe), si no costo por línea,
        si no costo global del mapa.
    Puedes pasar 'costos_transbordo_por_estacion' para granularidad fina:
      {"pino suarez": 300, "hidalgo": 400, ...} (nombres tal como vienen en el JSON).
    """
    grafo: Dict[Tuple[str, str], List[Tuple[Tuple[str, str], int]]] = {}

    def nodo(linea_nombre: str, est_nombre: str) -> Tuple[str, str]:
        return (linea_nombre, normaliza(est_nombre))

    costos_transbordo_por_estacion = costos_transbordo_por_estacion or {}

    # Índice para obtener costo por línea
    costo_linea: Dict[str, int] = {}
    for ln in mapa.lineas:
        # si la línea no define costo, usa global
        costo_linea[ln.nombre] = ln.costo_transbordo_linea if ln.costo_transbordo_linea is not None else mapa.costo_transbordo_global

    for ln in mapa.lineas:
        for e in ln.estaciones:
            u = nodo(ln.nombre, e.nombre)
            grafo.setdefault(u, [])

            # anterior
            if e.ant_estacion is not None and e.distancia_ant is not None:
                v = nodo(ln.nombre, e.ant_estacion)
                grafo[u].append((v, int(e.distancia_ant)))

            # siguiente
            if e.sig_estacion is not None and e.distancia_sig is not None:
                v = nodo(ln.nombre, e.sig_estacion)
                grafo[u].append((v, int(e.distancia_sig)))

            # transbordos
            for (linea_dest, est_dest) in e.transbordos:
                v = nodo(linea_dest, est_dest)
                # prioridad de costos: por estación -> por línea origen -> global
                costo_est = costos_transbordo_por_estacion.get(normaliza(e.nombre))
                if costo_est is not None:
                    costo_t = int(costo_est)
                else:
                    costo_t = int(costo_linea.get(ln.nombre, mapa.costo_transbordo_global))
                grafo[u].append((v, costo_t))

    return grafo

# ====== Construir grafo directamente desde JSON ======
def construir_grafo_desde_json(
    ruta_json: str,
    costos_transbordo_por_estacion: Optional[Dict[str, int]] = None
) -> Dict[Tuple[str, str], List[Tuple[Tuple[str, str], int]]]:
    mapa = iniciar_mapa(ruta_json)
    return construir_grafo_desde_mapa(mapa, costos_transbordo_por_estacion=costos_transbordo_por_estacion)

# ====== Dijkstra ======
def dijkstra_multi(grafo, origenes: List[Tuple[str, str]], destino_est_norm: str) -> Tuple[Optional[List[Tuple[str, str]]], Optional[int]]:
    destinos_set: Set[Tuple[str, str]] = {n for n in grafo.keys() if n[1] == destino_est_norm}
    if not destinos_set:
        return None, None

    dist: Dict[Tuple[str, str], int] = {}
    prev: Dict[Tuple[str, str], Optional[Tuple[str, str]]] = {}
    pq = []

    for o in origenes:
        dist[o] = 0
        prev[o] = None
        heapq.heappush(pq, (0, o))

    visitados: Set[Tuple[str, str]] = set()

    while pq:
        d, u = heapq.heappop(pq)
        if u in visitados:
            continue
        visitados.add(u)

        if u in destinos_set:
            ruta = []
            cur = u
            while cur is not None:
                ruta.append(cur)
                cur = prev.get(cur)
            ruta.reverse()
            return ruta, d

        for v, w in grafo.get(u, []):
            nd = d + w
            if nd < dist.get(v, float('inf')):
                dist[v] = nd
                prev[v] = u
                heapq.heappush(pq, (nd, v))

    return None, None

# ====== Parser de prompt ======
def extrae_estaciones_de_prompt(prompt: str, nombres_estaciones: List[str]) -> Tuple[Optional[str], Optional[str], List[str]]:
    p = normaliza(prompt)
    for k, v in SINONIMOS.items():
        p = p.replace(normaliza(k), normaliza(v))

    encontradas = []
    for n in nombres_estaciones:
        nn = normaliza(n)
        if nn in p and nn not in encontradas:
            encontradas.append(nn)

    if len(encontradas) < 2:
        tokens = re.findall(r"[a-zA-Záéíóúñü]+(?: [a-zA-Záéíóúñü]+)*", p)
        candidatos = set()
        lista_norm = [normaliza(x) for x in nombres_estaciones]
        for t in tokens:
            t_norm = normaliza(t)
            match = difflib.get_close_matches(t_norm, lista_norm, n=1, cutoff=0.88)
            if match:
                candidatos.add(match[0])
        for c in candidatos:
            if c not in encontradas:
                encontradas.append(c)

    origen, destino = None, None
    patrones = [
        r"de\s+(.*?)\s+a\s+(.*)",
        r"desde\s+(.*?)\s+hasta\s+(.*)",
        r"ir\s+a\s+(.*?)\s+desde\s+(.*)"
    ]
    for pat in patrones:
        m = re.search(pat, p)
        if m:
            o_raw, d_raw = m.group(1).strip(), m.group(2).strip()
            o = normaliza(aplica_sinonimos(o_raw))
            d = normaliza(aplica_sinonimos(d_raw))
            lista_norm = [normaliza(x) for x in nombres_estaciones]
            o_match = difflib.get_close_matches(o, lista_norm, n=1, cutoff=0.8)
            d_match = difflib.get_close_matches(d, lista_norm, n=1, cutoff=0.8)
            origen = o_match[0] if o_match else None
            destino = d_match[0] if d_match else None
            break

    if origen is None and len(encontradas) >= 1:
        origen = encontradas[0]
    if destino is None and len(encontradas) >= 2:
        destino = encontradas[1]

    return origen, destino, encontradas

def nombres_estaciones_de_json(ruta_json: str) -> List[str]:
    data = cargar_conocimiento_desde_archivo(ruta_json)
    out = []
    for _, info_linea in data.get("lineas", {}).items():
        out.extend(list(info_linea.get("estaciones", {}).keys()))
    return out

def formatea_instrucciones(ruta: List[Tuple[str, str]], distancia_total: int) -> str:
    if not ruta:
        return "No se encontró ruta."
    segmentos = []
    cur_line = ruta[0][0]
    start_station = ruta[0][1]
    for i in range(1, len(ruta)):
        line_i, est_i = ruta[i]
        prev_line, prev_est = ruta[i-1]
        if line_i != prev_line:
            segmentos.append((cur_line, start_station, prev_est))
            cur_line = line_i
            start_station = est_i
    segmentos.append((cur_line, start_station, ruta[-1][1]))
    instrucciones = []
    for (ln, a, b) in segmentos:
        instrucciones.append(f"• Toma {ln} desde '{a}' hasta '{b}'.")
    instrucciones.append(f"Distancia total estimada: {distancia_total} m")
    return "\n".join(instrucciones)

# ====== Función principal (lee costo desde JSON automáticamente) ======
def resolver_ruta(prompt: str, ruta_json: str) -> str:
    grafo = construir_grafo_desde_json(ruta_json)
    lista_estaciones = nombres_estaciones_de_json(ruta_json)

    origen, destino, encontradas = extrae_estaciones_de_prompt(prompt, lista_estaciones)
    if not origen or not destino:
        return (
            "No pude identificar claramente origen/destino.\n"
            f"Detecté: {', '.join(encontradas) if encontradas else 'ninguna'}.\n"
            "Incluye algo como: 'de Observatorio a Zócalo' o 'desde Tacubaya hasta Pino Suárez'."
        )

    origenes = [n for n in grafo.keys() if n[1] == origen]
    if not origenes:
        return f"La estación de origen '{origen}' no está en el mapa."
    destinos_norm = destino
    destinos = [n for n in grafo.keys() if n[1] == destinos_norm]
    if not destinos:
        return f"La estación de destino '{destino}' no está en el mapa."

    ruta, dist_total = dijkstra_multi(grafo, origenes, destinos_norm)
    if not ruta:
        return "No hay ruta conectada entre esas estaciones (con las líneas cargadas)."
    return formatea_instrucciones(ruta, dist_total)

# ====== Ejemplo de uso ======
if __name__ == "__main__":
    ruta_json = "metro_cdmx.json"  # tu archivo

    # Ejemplo de JSON con costo global:
    # {
    #   "costo_transbordo": 250,
    #   "lineas": { ... }
    # }

    ejemplos = [
        "Quiero ir de Observatorio a Zócalo",
        "¿Cómo llego desde Tacubaya hasta Pino Suárez en el metro?",
        "de merced a tasqueña",
        "Desde Balderas hasta Allende",
    ]
    for p in ejemplos:
        print(f"\nPrompt: {p}")
        print(resolver_ruta(p, ruta_json))
