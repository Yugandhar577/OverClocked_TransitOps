import { useCallback, useEffect, useMemo, useState } from 'react'
import { AlertTriangle, Crosshair, LocateFixed, Radio, Search, Signal, Truck } from 'lucide-react'

import { API_BASE_URL, api, currentToken, messageFrom } from '../api'
import { FleetTrackingMap } from './FleetTrackingMap'
import type { FleetVehicle, Geofence, LocationPoint, TrackingAlert } from './types'


const relativeTime = (value: string | null) => {
  if (!value) return 'No GPS fix'
  const seconds = Math.max(0, Math.round((Date.now() - new Date(value).getTime()) / 1000))
  if (seconds < 60) return `Updated ${seconds}s ago`
  if (seconds < 3600) return `${Math.round(seconds / 60)} min ago`
  return `${Math.round(seconds / 3600)} hr ago`
}

const freshnessClass = (status: string) => `freshness-badge freshness-${status.toLowerCase()}`

export function FleetTrackingPage({ onNavigate }: { onNavigate: (page: string) => void }) {
  const [fleet, setFleet] = useState<FleetVehicle[]>([])
  const [alerts, setAlerts] = useState<TrackingAlert[]>([])
  const [geofences, setGeofences] = useState<Geofence[]>([])
  const [history, setHistory] = useState<LocationPoint[]>([])
  const [routeCoordinates, setRouteCoordinates] = useState<[number, number][]>([])
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [query, setQuery] = useState('')
  const [vehicleType, setVehicleType] = useState('All')
  const [region, setRegion] = useState('All')
  const [trackingState, setTrackingState] = useState('All')
  const [movement, setMovement] = useState('All')
  const [driver, setDriver] = useState('All')
  const [depot, setDepot] = useState('All')
  const [vehicleStatus, setVehicleStatus] = useState('All')
  const [tripStatus, setTripStatus] = useState('All')
  const [mapProvider, setMapProvider] = useState<'openstreetmap' | 'mapbox' | 'google'>('openstreetmap')
  const [autoFollow, setAutoFollow] = useState(false)
  const [fitRequest, setFitRequest] = useState(1)
  const [error, setError] = useState('')
  const [liveConnected, setLiveConnected] = useState(false)

  const load = useCallback(async () => {
    try {
      const [fleetResult, alertsResult, geofenceResult, configResult] = await Promise.all([api.get('/tracking/fleet/latest'), api.get('/tracking/alerts'), api.get('/geofences'), api.get('/tracking/config')])
      setFleet(fleetResult.data); setAlerts(alertsResult.data); setGeofences(geofenceResult.data); setError('')
      setMapProvider(configResult.data.map_provider || 'openstreetmap')
      setSelectedId((current) => current || fleetResult.data[0]?.vehicle_id || null)
    } catch (reason) { setError(messageFrom(reason)) }
  }, [])

  useEffect(() => {
    load()
    const poll = window.setInterval(load, 20_000)
    return () => window.clearInterval(poll)
  }, [load])

  useEffect(() => {
    const controller = new AbortController()
    const token = currentToken()
    if (!token) return () => controller.abort()
    const connect = async () => {
      try {
        const response = await fetch(`${API_BASE_URL}/tracking/events`, { headers: { Authorization: `Bearer ${token}` }, signal: controller.signal })
        if (!response.ok || !response.body) throw new Error('Live stream unavailable')
        setLiveConnected(true)
        const reader = response.body.getReader(); const decoder = new TextDecoder(); let buffer = ''
        while (true) {
          const { value, done } = await reader.read()
          if (done) break
          buffer += decoder.decode(value, { stream: true })
          const messages = buffer.split('\n\n'); buffer = messages.pop() || ''
          messages.forEach((message) => {
            const line = message.split('\n').find((item) => item.startsWith('data: '))
            if (!line) return
            const event = JSON.parse(line.slice(6))
            if (event.type !== 'vehicle_location') return
            setFleet((current) => current.map((vehicle) => vehicle.vehicle_id === event.vehicle_id ? { ...vehicle, latitude: event.latitude, longitude: event.longitude, speed_mps: event.speed_mps, accuracy_meters: event.accuracy_meters, captured_at: event.captured_at, received_at: new Date().toISOString(), freshness_status: 'ONLINE', movement_status: (event.speed_mps || 0) >= 1.4 ? 'MOVING' : 'STOPPED' } : vehicle))
          })
        }
      } catch {
        if (!controller.signal.aborted) setLiveConnected(false)
      }
    }
    connect()
    return () => controller.abort()
  }, [])

  const selectedTripId = fleet.find((item) => item.vehicle_id === selectedId)?.trip_id

  useEffect(() => {
    if (!selectedId) { setHistory([]); return }
    Promise.all([api.get(`/tracking/vehicles/${selectedId}/history?limit=80`), selectedTripId ? api.get(`/tracking/trips/${selectedTripId}/route`) : Promise.resolve({ data: { coordinates: [] } })])
      .then(([historyResult, routeResult]) => { setHistory(historyResult.data); setRouteCoordinates(routeResult.data.coordinates) })
      .catch(() => { setHistory([]); setRouteCoordinates([]) })
  }, [selectedId, selectedTripId])

  const filtered = useMemo(() => fleet.filter((vehicle) => {
    const searchable = `${vehicle.vehicle_name} ${vehicle.registration} ${vehicle.driver_name || ''} ${vehicle.trip_id}`.toLowerCase()
    return searchable.includes(query.toLowerCase())
      && (vehicleType === 'All' || vehicle.vehicle_type === vehicleType)
      && (region === 'All' || vehicle.region === region)
      && (trackingState === 'All' || vehicle.freshness_status === trackingState)
      && (movement === 'All' || vehicle.movement_status === movement)
      && (driver === 'All' || vehicle.driver_name === driver)
      && (depot === 'All' || vehicle.depot === depot)
      && (vehicleStatus === 'All' || vehicle.vehicle_status === vehicleStatus)
      && (tripStatus === 'All' || vehicle.trip_status === tripStatus)
  }), [depot, driver, fleet, movement, query, region, trackingState, tripStatus, vehicleStatus, vehicleType])
  const selected = fleet.find((vehicle) => vehicle.vehicle_id === selectedId) || null
  const activeCount = fleet.filter((vehicle) => vehicle.freshness_status === 'ONLINE').length
  const movingCount = fleet.filter((vehicle) => vehicle.movement_status === 'MOVING').length

  return <div className="tracking-page">
    <section className="page-header tracking-header"><div><p className="eyebrow">LIVE FLEET TRACKING</p><h1>Every active vehicle, one operational view</h1><p className="muted">Server-authorized driver-phone locations with live updates and polling fallback.</p></div><div className="tracking-live-state"><span className={liveConnected ? 'live-pulse' : 'live-pulse offline'}/>{liveConnected ? 'Live stream connected' : 'Polling fallback active'}</div></section>
    {error && <div className="tracking-error">{error}</div>}
    <section className="tracking-kpis"><article><Signal/><div><b>{activeCount}</b><span>Online vehicles</span></div></article><article><Truck/><div><b>{movingCount}</b><span>Moving now</span></div></article><article><AlertTriangle/><div><b>{alerts.length}</b><span>Open alerts</span></div></article></section>
    <div className="tracking-toolbar">
      <label className="tracking-search"><Search size={16}/><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search vehicle, driver, trip"/></label>
      <select value={vehicleType} onChange={(event) => setVehicleType(event.target.value)}><option>All</option>{Array.from(new Set(fleet.map((vehicle) => vehicle.vehicle_type))).map((value) => <option key={value}>{value}</option>)}</select>
      <select value={region} onChange={(event) => setRegion(event.target.value)}><option>All</option>{Array.from(new Set(fleet.map((vehicle) => vehicle.region))).map((value) => <option key={value}>{value}</option>)}</select>
      <select value={trackingState} onChange={(event) => setTrackingState(event.target.value)}><option>All</option><option>ONLINE</option><option>STALE</option><option>OFFLINE</option></select>
      <select value={movement} onChange={(event) => setMovement(event.target.value)}><option>All</option><option>MOVING</option><option>STOPPED</option><option>GPS_UNAVAILABLE</option></select>
      <select aria-label="Driver" value={driver} onChange={(event) => setDriver(event.target.value)}><option>All</option>{Array.from(new Set(fleet.map((vehicle) => vehicle.driver_name).filter((value): value is string => Boolean(value)))).map((value) => <option key={value}>{value}</option>)}</select>
      <select aria-label="Depot" value={depot} onChange={(event) => setDepot(event.target.value)}><option>All</option>{Array.from(new Set(fleet.map((vehicle) => vehicle.depot))).map((value) => <option key={value}>{value}</option>)}</select>
      <select aria-label="Vehicle status" value={vehicleStatus} onChange={(event) => setVehicleStatus(event.target.value)}><option>All</option>{Array.from(new Set(fleet.map((vehicle) => vehicle.vehicle_status))).map((value) => <option key={value}>{value}</option>)}</select>
      <select aria-label="Trip status" value={tripStatus} onChange={(event) => setTripStatus(event.target.value)}><option>All</option>{Array.from(new Set(fleet.map((vehicle) => vehicle.trip_status))).map((value) => <option key={value}>{value}</option>)}</select>
      <button className="secondary" onClick={() => setFitRequest((value) => value + 1)}><Crosshair size={16}/> Auto fit active fleet</button>
      <button className={`secondary ${autoFollow ? 'toggle-active' : ''}`} disabled={!selected} onClick={() => setAutoFollow((value) => !value)}><LocateFixed size={16}/> Auto follow</button>
    </div>
    <section className="tracking-workspace">
      <aside className="fleet-tracking-sidebar">
        <div className="tracking-section-title"><b>Authorized fleet</b><span>{filtered.length} vehicles</span></div>
        <div className="fleet-tracking-list">{filtered.map((vehicle) => <button key={vehicle.vehicle_id} className={selectedId === vehicle.vehicle_id ? 'selected' : ''} onClick={() => { setSelectedId(vehicle.vehicle_id); setAutoFollow(false) }}><span className={`vehicle-list-icon movement-${vehicle.movement_status.toLowerCase()}`}><Truck size={17}/></span><span className="vehicle-list-main"><b>{vehicle.vehicle_name}</b><small>{vehicle.registration} · {vehicle.trip_id}</small><small>{vehicle.driver_name || 'Driver details restricted'}</small></span><span className="vehicle-list-state"><i className={freshnessClass(vehicle.freshness_status)}>{vehicle.freshness_status}</i><small>{relativeTime(vehicle.received_at)}</small></span></button>)}</div>
      </aside>
      <div className="fleet-map-panel"><FleetTrackingMap vehicles={filtered} selectedVehicleId={selectedId} onSelect={setSelectedId} autoFollow={autoFollow} fitRequest={fitRequest} history={history} geofences={geofences} routeCoordinates={routeCoordinates} provider={mapProvider}/></div>
      <aside className="vehicle-tracking-details">{selected ? <>
        <div className="tracking-section-title"><b>{selected.vehicle_name}</b><i className={freshnessClass(selected.freshness_status)}>{selected.freshness_status}</i></div>
        <p className="tracking-registration">{selected.registration} · {selected.vehicle_type}</p>
        <dl><div><dt>Trip</dt><dd>{selected.trip_id} · {selected.trip_status}</dd></div><div><dt>Driver</dt><dd>{selected.driver_name || 'Restricted'}</dd></div><div><dt>Route</dt><dd>{selected.source} → {selected.destination}</dd></div><div><dt>Movement</dt><dd>{selected.movement_status} · {selected.speed_mps !== null ? `${Math.round(selected.speed_mps * 3.6)} km/h` : 'No speed'}</dd></div><div><dt>GPS accuracy</dt><dd>{selected.accuracy_meters !== null ? `±${Math.round(selected.accuracy_meters)} m` : 'Unavailable'}</dd></div><div><dt>Remaining</dt><dd>{selected.remaining_distance_km !== null ? `~${selected.remaining_distance_km} km` : 'Awaiting route position'}</dd></div><div><dt>Last update</dt><dd>{relativeTime(selected.received_at)}</dd></div></dl>
        <div className="route-progress"><span style={{ width: `${selected.remaining_distance_km !== null ? Math.max(5, 100 - selected.remaining_distance_km / Math.max(1, 100) * 100) : 5}%` }}/></div>
        <div className="record-links"><button onClick={() => onNavigate('Fleet')}>Vehicle record</button><button onClick={() => onNavigate('Drivers')}>Driver record</button><button onClick={() => onNavigate('Trips')}>Trip record</button></div>
        <div className="history-summary"><Radio size={15}/><span>{history.length} recent GPS points</span></div>
      </> : <div className="tracking-empty">Select a vehicle to inspect its tracking details.</div>}</aside>
    </section>
    <section className="tracking-alert-panel panel"><div className="tracking-section-title"><b>Tracking alerts</b><span>Deduplicated operational events</span></div><div className="tracking-alert-list">{alerts.length ? alerts.map((alert) => <article key={alert.id} className={`alert-${alert.severity.toLowerCase()}`}><AlertTriangle size={17}/><div><b>{alert.alert_type.replaceAll('_', ' ')}</b><p>{alert.message}</p><small>{relativeTime(alert.created_at)}</small></div></article>) : <p className="tracking-empty">No active tracking alerts.</p>}</div></section>
  </div>
}
