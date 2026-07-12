export type FleetVehicle = {
  vehicle_id: string
  vehicle_name: string
  registration: string
  vehicle_type: string
  vehicle_status: string
  region: string
  depot: string
  driver_id: string
  driver_name: string | null
  trip_id: string
  trip_status: string
  source: string
  destination: string
  source_coordinates: [number, number] | null
  destination_coordinates: [number, number] | null
  latitude: number | null
  longitude: number | null
  speed_mps: number | null
  heading_degrees: number | null
  accuracy_meters: number | null
  captured_at: string | null
  received_at: string | null
  freshness_status: 'ONLINE' | 'STALE' | 'OFFLINE'
  movement_status: 'MOVING' | 'STOPPED' | 'GPS_UNAVAILABLE'
  remaining_distance_km: number | null
  distance_is_approximate: boolean
}

export type LocationPoint = {
  id: string
  latitude: number
  longitude: number
  accuracy_meters: number
  speed_mps: number | null
  heading_degrees: number | null
  captured_at: string
  source: string
}

export type TrackingAlert = {
  id: string
  vehicle_id: string | null
  trip_id: string | null
  alert_type: string
  severity: string
  message: string
  created_at: string
}

export type Geofence = {
  id: string
  depot_id: string
  name: string
  type: string
  center_latitude: number
  center_longitude: number
  radius_meters: number
  is_active: boolean
}

export type DriverActiveTrip = {
  trip: {
    id: string
    status: string
    source: string
    destination: string
    planned_distance_km: number
    source_coordinates: [number, number] | null
    destination_coordinates: [number, number] | null
  }
  vehicle: { id: string; name: string; registration: string }
  driver: { id: string; name: string }
  tracking_session: { id: string; status: string; last_location_at: string | null } | null
  settings: {
    update_interval_seconds: number
    stationary_interval_seconds: number
    minimum_movement_meters: number
    allow_pause: boolean
    map_provider: 'openstreetmap' | 'mapbox' | 'google'
    directions_provider: string
  }
}

export type LocationSubmission = {
  idempotency_key: string
  latitude: number
  longitude: number
  accuracy_meters: number
  altitude: number | null
  altitude_accuracy: number | null
  heading_degrees: number | null
  speed_mps: number | null
  captured_at: string
  battery_percentage: number | null
  network_state: string
}
