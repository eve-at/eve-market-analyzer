"""Courier path optimization handler"""
import mysql.connector
from mysql.connector import Error
import importlib
from collections import defaultdict
import heapq
import requests
from datetime import datetime


def _get_db_config():
    """Reload and get DB_CONFIG from settings module"""
    import settings
    importlib.reload(settings)
    return settings.DB_CONFIG


def search_solar_systems(query):
    """Search solar systems by name

    Args:
        query: Search query string (min 3 characters)

    Returns:
        dict: {system_name: system_id} mapping (max 5 results)
    """
    if len(query) < 3:
        return {}

    systems = {}

    try:
        db_config = _get_db_config()
        connection = mysql.connector.connect(**db_config)

        if connection.is_connected():
            cursor = connection.cursor()

            # Search for systems matching the query
            query_pattern = f"%{query}%"
            cursor.execute("""
                SELECT solarSystemName, solarSystemID
                FROM solar_systems
                WHERE solarSystemName LIKE %s
                ORDER BY solarSystemName
                LIMIT 5
            """, (query_pattern,))

            results = cursor.fetchall()
            systems = {name: system_id for name, system_id in results}

    except Error as e:
        print(f"Database error: {e}")
    finally:
        if connection and connection.is_connected():
            cursor.close()
            connection.close()

    return systems


def search_stations(query):
    """Search stations by name

    Args:
        query: Search query string (min 3 characters)

    Returns:
        dict: {station_name: (station_id, solar_system_id)} mapping (max 5 results)
    """
    if len(query) < 3:
        return {}

    stations = {}

    try:
        db_config = _get_db_config()
        connection = mysql.connector.connect(**db_config)

        if connection.is_connected():
            cursor = connection.cursor()

            # Search for stations matching the query
            query_pattern = f"%{query}%"
            cursor.execute("""
                SELECT stationName, stationID, solarSystemID
                FROM stations
                WHERE stationName LIKE %s
                ORDER BY stationName
                LIMIT 5
            """, (query_pattern,))

            results = cursor.fetchall()
            stations = {name: (station_id, system_id) for name, station_id, system_id in results}

    except Error as e:
        print(f"Database error: {e}")
    finally:
        if connection and connection.is_connected():
            cursor.close()
            connection.close()

    return stations


def build_jump_graph():
    """Build a graph of solar system jumps

    Returns:
        dict: {from_system_id: [to_system_id, ...]}
    """
    graph = defaultdict(list)

    try:
        db_config = _get_db_config()
        connection = mysql.connector.connect(**db_config)

        if connection.is_connected():
            cursor = connection.cursor()

            # Load all jumps
            cursor.execute("""
                SELECT fromSolarSystemID, toSolarSystemID
                FROM solar_system_jumps
            """)

            jumps = cursor.fetchall()

            # Build bidirectional graph
            for from_system, to_system in jumps:
                graph[from_system].append(to_system)
                # Add reverse direction (graph is symmetric)
                graph[to_system].append(from_system)

    except Error as e:
        print(f"Database error: {e}")
    finally:
        if connection and connection.is_connected():
            cursor.close()
            connection.close()

    return graph


def dijkstra_shortest_path(graph, start, end):
    """Find shortest path using Dijkstra's algorithm

    Args:
        graph: Graph as adjacency list
        start: Start node
        end: End node

    Returns:
        tuple: (distance, path) where distance is jump count and path is list of nodes
    """
    if start == end:
        return 0, [start]

    # Priority queue: (distance, node, path)
    queue = [(0, start, [start])]
    visited = set()

    while queue:
        distance, current, path = heapq.heappop(queue)

        if current in visited:
            continue

        visited.add(current)

        if current == end:
            return distance, path

        # Explore neighbors
        for neighbor in graph.get(current, []):
            if neighbor not in visited:
                heapq.heappush(queue, (distance + 1, neighbor, path + [neighbor]))

    # No path found
    return float('inf'), []


def calculate_all_pair_distances(graph, systems):
    """Calculate shortest distances between all pairs of systems

    Args:
        graph: Graph as adjacency list
        systems: List of system IDs

    Returns:
        dict: {(from_id, to_id): (distance, path)}
    """
    distances = {}

    for i, system1 in enumerate(systems):
        for system2 in systems[i:]:
            if system1 == system2:
                distances[(system1, system2)] = (0, [system1])
                distances[(system2, system1)] = (0, [system2])
            else:
                dist, path = dijkstra_shortest_path(graph, system1, system2)
                distances[(system1, system2)] = (dist, path)
                distances[(system2, system1)] = (dist, list(reversed(path)))

    return distances


def optimize_route_greedy(start_system_id, destination_system_ids, distances):
    """Optimize route using greedy nearest-neighbor algorithm

    Args:
        start_system_id: Starting system ID
        destination_system_ids: List of destination system IDs (in any order)
        distances: Precomputed distances dict

    Returns:
        tuple: (total_jumps, ordered_system_ids) where ordered_system_ids starts with start_system_id
    """
    if not destination_system_ids:
        return 0, [start_system_id]

    # Greedy nearest neighbor
    current = start_system_id
    remaining = set(destination_system_ids)
    route = [current]
    total_jumps = 0

    while remaining:
        # Find nearest unvisited destination
        nearest = min(remaining, key=lambda dest: distances.get((current, dest), (float('inf'),))[0])
        dist = distances.get((current, nearest), (float('inf'),))[0]

        if dist == float('inf'):
            # No path exists
            return float('inf'), []

        total_jumps += dist
        route.append(nearest)
        remaining.remove(nearest)
        current = nearest

    return total_jumps, route


def get_station_info(station_ids):
    """Get station information by IDs

    Args:
        station_ids: List of station IDs

    Returns:
        dict: {station_id: {'stationName': str, 'solarSystemID': int, 'solarSystemName': str, 'security': float}}
    """
    if not station_ids:
        return {}

    stations_info = {}

    try:
        db_config = _get_db_config()
        connection = mysql.connector.connect(**db_config)

        if connection.is_connected():
            cursor = connection.cursor()

            # Get station info with solar system names and security
            placeholders = ','.join(['%s'] * len(station_ids))
            query = f"""
                SELECT s.stationID, s.stationName, s.solarSystemID, ss.solarSystemName, ss.security
                FROM stations s
                JOIN solar_systems ss ON s.solarSystemID = ss.solarSystemID
                WHERE s.stationID IN ({placeholders})
            """
            cursor.execute(query, tuple(station_ids))

            results = cursor.fetchall()
            for station_id, station_name, system_id, system_name, security in results:
                stations_info[station_id] = {
                    'stationName': station_name,
                    'solarSystemID': system_id,
                    'solarSystemName': system_name,
                    'security': float(security) if security is not None else 0.0
                }

    except Error as e:
        print(f"Database error: {e}")
    finally:
        if connection and connection.is_connected():
            cursor.close()
            connection.close()

    return stations_info


def optimize_courier_route(start_system_id, destination_station_ids):
    """Optimize courier route for delivering to multiple stations

    Args:
        start_system_id: Starting solar system ID
        destination_station_ids: List of destination station IDs (order will be optimized)

    Returns:
        dict: {
            'success': bool,
            'total_jumps': int,
            'route': [
                {
                    'station_id': int,
                    'station_name': str,
                    'system_id': int,
                    'system_name': str,
                    'jumps_from_previous': int
                },
                ...
            ]
        }
    """
    try:
        # Get station info
        stations_info = get_station_info(destination_station_ids)

        if not stations_info:
            return {'success': False, 'error': 'Failed to load station information'}

        # Extract solar system IDs from stations
        destination_system_ids = list(set(info['solarSystemID'] for info in stations_info.values()))

        # Build jump graph
        graph = build_jump_graph()

        # Calculate all distances
        all_systems = [start_system_id] + destination_system_ids
        distances = calculate_all_pair_distances(graph, all_systems)

        # Optimize route
        total_jumps, optimized_system_order = optimize_route_greedy(
            start_system_id,
            destination_system_ids,
            distances
        )

        if total_jumps == float('inf'):
            return {'success': False, 'error': 'No valid route found'}

        # Build route with station details
        route = []
        full_path = []  # Complete path with all transit systems

        for i, system_id in enumerate(optimized_system_order):
            # Find stations in this system
            system_stations = [
                (sid, info) for sid, info in stations_info.items()
                if info['solarSystemID'] == system_id
            ]

            # Calculate jumps from previous system and get full path
            jumps_from_prev = 0
            path_segment = []
            if i > 0:
                prev_system = optimized_system_order[i - 1]
                jumps_from_prev, path_segment = distances.get((prev_system, system_id), (0, []))

            # Add path segment to full path
            # For the first iteration (i == 0), skip adding the start system entirely
            # For subsequent iterations, add the path segment excluding the first system (it's the previous destination)
            if i > 0 and path_segment:
                full_path.extend(path_segment[1:])  # Skip first system (it's the previous destination)

            # Add all stations in this system to route
            for station_id, info in system_stations:
                route.append({
                    'station_id': station_id,
                    'station_name': info['stationName'],
                    'system_id': system_id,
                    'system_name': info['solarSystemName'],
                    'security': info['security'],
                    'jumps_from_previous': jumps_from_prev if station_id == system_stations[0][0] else 0
                })

        # Get security info for all systems in full path
        full_path_with_security = []
        if full_path:
            try:
                db_config = _get_db_config()
                connection = mysql.connector.connect(**db_config)

                if connection.is_connected():
                    cursor = connection.cursor()

                    placeholders = ','.join(['%s'] * len(full_path))
                    query = f"""
                        SELECT solarSystemID, solarSystemName, security
                        FROM solar_systems
                        WHERE solarSystemID IN ({placeholders})
                    """
                    cursor.execute(query, tuple(full_path))

                    systems_dict = {}
                    for sys_id, sys_name, sec in cursor.fetchall():
                        systems_dict[sys_id] = {
                            'system_id': sys_id,
                            'system_name': sys_name,
                            'security': float(sec) if sec is not None else 0.0
                        }

                    # Build full path in order
                    destination_system_ids = [s['system_id'] for s in route]
                    for sys_id in full_path:
                        if sys_id in systems_dict:
                            sys_info = systems_dict[sys_id]
                            sys_info['is_destination'] = sys_id in destination_system_ids
                            full_path_with_security.append(sys_info)

                    cursor.close()
                    connection.close()
            except Exception as e:
                print(f"Error getting full path security: {e}")

        return {
            'success': True,
            'total_jumps': total_jumps,
            'route': route,
            'full_path': full_path_with_security
        }

    except Exception as e:
        print(f"Error optimizing route: {e}")
        import traceback
        traceback.print_exc()
        return {'success': False, 'error': str(e)}


def refresh_access_token(refresh_token):
    """Refresh EVE Online access token

    Args:
        refresh_token: Refresh token from database

    Returns:
        dict: {'access_token': str, 'token_expiry': datetime} or None
    """
    try:
        import settings
        importlib.reload(settings)

        url = "https://login.eveonline.com/v2/oauth/token"
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Host": "login.eveonline.com"
        }
        data = {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": settings.EVE_CLIENT_ID
        }

        response = requests.post(url, headers=headers, data=data, timeout=10)
        response.raise_for_status()

        token_data = response.json()
        access_token = token_data.get('access_token')
        expires_in = token_data.get('expires_in', 1200)

        # Calculate expiry time
        from datetime import timedelta
        token_expiry = datetime.now() + timedelta(seconds=expires_in)

        return {
            'access_token': access_token,
            'token_expiry': token_expiry
        }

    except Exception as e:
        print(f"Error refreshing token: {e}")
        return None


def get_character_location(character_id, access_token):
    """Get character's current location from ESI

    Args:
        character_id: Character ID
        access_token: Valid access token

    Returns:
        dict: {'solar_system_id': int, 'solar_system_name': str} or None
    """
    try:
        # Get location from ESI
        url = f"https://esi.evetech.net/latest/characters/{character_id}/location/"
        headers = {
            "Authorization": f"Bearer {access_token}"
        }
        params = {
            "datasource": "tranquility"
        }

        response = requests.get(url, headers=headers, params=params, timeout=10)
        response.raise_for_status()

        location_data = response.json()
        solar_system_id = location_data.get('solar_system_id')

        if not solar_system_id:
            return None

        # Get system name from database
        db_config = _get_db_config()
        connection = mysql.connector.connect(**db_config)

        if connection.is_connected():
            cursor = connection.cursor()

            cursor.execute("""
                SELECT solarSystemName
                FROM solar_systems
                WHERE solarSystemID = %s
            """, (solar_system_id,))

            result = cursor.fetchone()

            if result:
                system_name = result[0]
                return {
                    'solar_system_id': solar_system_id,
                    'solar_system_name': system_name
                }

        return None

    except Exception as e:
        print(f"Error getting character location: {e}")
        return None
    finally:
        if connection and connection.is_connected():
            cursor.close()
            connection.close()
