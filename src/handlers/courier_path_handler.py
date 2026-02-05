"""Courier path optimization handler"""
import sqlite3
import os
import importlib
from collections import defaultdict
import heapq
import requests
from datetime import datetime


def _get_db_path():
    """Reload and get DB_PATH from settings module"""
    import settings
    importlib.reload(settings)
    return settings.DB_PATH


def _get_connection():
    """Get a SQLite connection"""
    db_path = _get_db_path()
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


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
    conn = None

    try:
        conn = _get_connection()
        cursor = conn.cursor()

        query_pattern = f"%{query}%"
        cursor.execute("""
            SELECT solarSystemName, solarSystemID
            FROM solar_systems
            WHERE solarSystemName LIKE ?
            ORDER BY solarSystemName
            LIMIT 5
        """, (query_pattern,))

        results = cursor.fetchall()
        systems = {row['solarSystemName']: row['solarSystemID'] for row in results}

    except Exception as e:
        print(f"Database error: {e}")
    finally:
        if conn:
            conn.close()

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
    conn = None

    try:
        conn = _get_connection()
        cursor = conn.cursor()

        query_pattern = f"%{query}%"
        cursor.execute("""
            SELECT stationName, stationID, solarSystemID
            FROM stations
            WHERE stationName LIKE ?
            ORDER BY stationName
            LIMIT 5
        """, (query_pattern,))

        results = cursor.fetchall()
        stations = {row['stationName']: (row['stationID'], row['solarSystemID']) for row in results}

    except Exception as e:
        print(f"Database error: {e}")
    finally:
        if conn:
            conn.close()

    return stations


def build_jump_graph():
    """Build a graph of solar system jumps

    Returns:
        dict: {from_system_id: [to_system_id, ...]}
    """
    graph = defaultdict(list)
    conn = None

    try:
        conn = _get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT fromSolarSystemID, toSolarSystemID
            FROM solar_system_jumps
        """)

        jumps = cursor.fetchall()

        for row in jumps:
            graph[row['fromSolarSystemID']].append(row['toSolarSystemID'])
            graph[row['toSolarSystemID']].append(row['fromSolarSystemID'])

    except Exception as e:
        print(f"Database error: {e}")
    finally:
        if conn:
            conn.close()

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
    """Calculate shortest distances between all pairs of systems"""
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
    """Optimize route using greedy nearest-neighbor algorithm"""
    if not destination_system_ids:
        return 0, [start_system_id]

    current = start_system_id
    remaining = set(destination_system_ids)
    route = [current]
    total_jumps = 0

    while remaining:
        nearest = min(remaining, key=lambda dest: distances.get((current, dest), (float('inf'),))[0])
        dist = distances.get((current, nearest), (float('inf'),))[0]

        if dist == float('inf'):
            return float('inf'), []

        total_jumps += dist
        route.append(nearest)
        remaining.remove(nearest)
        current = nearest

    return total_jumps, route


def get_station_info(station_ids):
    """Get station information by IDs"""
    if not station_ids:
        return {}

    stations_info = {}
    conn = None

    try:
        conn = _get_connection()
        cursor = conn.cursor()

        placeholders = ','.join(['?'] * len(station_ids))
        query = f"""
            SELECT s.stationID, s.stationName, s.solarSystemID, ss.solarSystemName, ss.security
            FROM stations s
            JOIN solar_systems ss ON s.solarSystemID = ss.solarSystemID
            WHERE s.stationID IN ({placeholders})
        """
        cursor.execute(query, tuple(station_ids))

        results = cursor.fetchall()
        for row in results:
            stations_info[row['stationID']] = {
                'stationName': row['stationName'],
                'solarSystemID': row['solarSystemID'],
                'solarSystemName': row['solarSystemName'],
                'security': float(row['security']) if row['security'] is not None else 0.0
            }

    except Exception as e:
        print(f"Database error: {e}")
    finally:
        if conn:
            conn.close()

    return stations_info


def optimize_courier_route(start_system_id, destination_station_ids):
    """Optimize courier route for delivering to multiple stations"""
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
        full_path = []

        for i, system_id in enumerate(optimized_system_order):
            system_stations = [
                (sid, info) for sid, info in stations_info.items()
                if info['solarSystemID'] == system_id
            ]

            jumps_from_prev = 0
            path_segment = []
            if i > 0:
                prev_system = optimized_system_order[i - 1]
                jumps_from_prev, path_segment = distances.get((prev_system, system_id), (0, []))

            if i > 0 and path_segment:
                full_path.extend(path_segment[1:])

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
            conn = None
            try:
                conn = _get_connection()
                cursor = conn.cursor()

                placeholders = ','.join(['?'] * len(full_path))
                query = f"""
                    SELECT solarSystemID, solarSystemName, security
                    FROM solar_systems
                    WHERE solarSystemID IN ({placeholders})
                """
                cursor.execute(query, tuple(full_path))

                systems_dict = {}
                for row in cursor.fetchall():
                    systems_dict[row['solarSystemID']] = {
                        'system_id': row['solarSystemID'],
                        'system_name': row['solarSystemName'],
                        'security': float(row['security']) if row['security'] is not None else 0.0
                    }

                destination_system_ids_set = {s['system_id'] for s in route}
                for sys_id in full_path:
                    if sys_id in systems_dict:
                        sys_info = systems_dict[sys_id]
                        sys_info['is_destination'] = sys_id in destination_system_ids_set
                        full_path_with_security.append(sys_info)

            except Exception as e:
                print(f"Error getting full path security: {e}")
            finally:
                if conn:
                    conn.close()

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
    """Refresh EVE Online access token"""
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
    """Get character's current location from ESI"""
    conn = None
    try:
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

        conn = _get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT solarSystemName
            FROM solar_systems
            WHERE solarSystemID = ?
        """, (solar_system_id,))

        result = cursor.fetchone()

        if result:
            return {
                'solar_system_id': solar_system_id,
                'solar_system_name': result['solarSystemName']
            }

        return None

    except Exception as e:
        print(f"Error getting character location: {e}")
        return None
    finally:
        if conn:
            conn.close()


def set_autopilot_waypoints(station_ids, access_token):
    """Set autopilot waypoints in-game via ESI API"""
    try:
        url = "https://esi.evetech.net/latest/ui/autopilot/waypoint/"

        for i, station_id in enumerate(station_ids):
            is_first = (i == 0)

            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json"
            }
            params = {
                "add_to_beginning": "true" if is_first else "false",
                "clear_other_waypoints": "true" if is_first else "false",
                "destination_id": station_id,
                "datasource": "tranquility"
            }

            response = requests.post(url, headers=headers, params=params, timeout=10)

            if response.status_code not in [204, 200]:
                response.raise_for_status()

        return {'success': True}

    except Exception as e:
        print(f"Error setting autopilot waypoints: {e}")
        return {'success': False, 'error': str(e)}
