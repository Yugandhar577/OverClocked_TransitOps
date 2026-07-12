import { useCallback, useEffect, useRef, useState } from 'react'
import { AlertOctagon, CheckCircle2, MapPin, Navigation, Pause, Play, Radio, Signal, Square } from 'lucide-react'

import { api, messageFrom } from '../api'
import { FleetTrackingMap } from './FleetTrackingMap'
import { pendingLocations, queueLocation, removePendingLocations } from './offlineQueue'
import type { DriverActiveTrip, FleetVehicle, LocationSubmission } from './types'


type BatteryNavigator = Navigator & { getBattery?: () => Promise<{ level: number }> }

const distanceMeters = (a: [number, number], b: [number, number]) => {
  const earth = 6_371_000; const toRadians = (value: number) => value * Math.PI / 180
  const dLat = toRadians(b[0] - a[0]); const dLon = toRadians(b[1] - a[1]); const lat1 = toRadians(a[0]); const lat2 = toRadians(b[0])
  const value = Math.sin(dLat / 2) ** 2 + Math.cos(lat1) * Math.cos(lat2) * Math.sin(dLon / 2) ** 2
  return earth * 2 * Math.atan2(Math.sqrt(value), Math.sqrt(1 - value))
}

export function DriverLiveTripPage() {
  const [activeTrip, setActiveTrip] = useState<DriverActiveTrip | null>(null)
  const [visibleFleet, setVisibleFleet] = useState<FleetVehicle[]>([])
  const [permission, setPermission] = useState<'idle' | 'requesting' | 'granted' | 'denied' | 'unavailable'>('idle')
  const [trackingStatus, setTrackingStatus] = useState<'NOT_STARTED' | 'ACTIVE' | 'PAUSED' | 'ENDED'>('NOT_STARTED')
  const [currentPosition, setCurrentPosition] = useState<[number, number] | null>(null)
  const [accuracy, setAccuracy] = useState<number | null>(null)
  const [offlineCount, setOfflineCount] = useState(0)
  const [networkOnline, setNetworkOnline] = useState(navigator.onLine)
  const [message, setMessage] = useState('')
  const [fitRequest, setFitRequest] = useState(1)
  const [routeCoordinates, setRouteCoordinates] = useState<[number, number][]>([])
  const watchId = useRef<number | null>(null)
  const lastSent = useRef<{ at: number; coordinates: [number, number]; heading: number | null } | null>(null)

  const load = useCallback(async () => {
    try {
      const [tripResult, fleetResult] = await Promise.all([api.get('/tracking/my-active-trip'), api.get('/tracking/my-visible-fleet')])
      setActiveTrip(tripResult.data); setVisibleFleet(fleetResult.data)
      const routeResult = await api.get(`/tracking/trips/${tripResult.data.trip.id}/route`)
      setRouteCoordinates(routeResult.data.coordinates)
      if (tripResult.data.tracking_session) setTrackingStatus(tripResult.data.tracking_session.status)
    } catch (reason) { setMessage(messageFrom(reason)) }
  }, [])

  const refreshQueueCount = useCallback(async () => setOfflineCount((await pendingLocations()).length), [])

  const flushQueue = useCallback(async () => {
    if (!navigator.onLine) return
    const pending = await pendingLocations()
    if (!pending.length) return
    try {
      await api.post('/tracking/locations/batch', { points: pending })
      await removePendingLocations(pending.map((point) => point.idempotency_key))
      setOfflineCount(0)
    } catch { setOfflineCount(pending.length) }
  }, [])

  useEffect(() => { load(); refreshQueueCount() }, [load, refreshQueueCount])
  useEffect(() => {
    const online = () => { setNetworkOnline(true); flushQueue() }
    const offline = () => setNetworkOnline(false)
    window.addEventListener('online', online); window.addEventListener('offline', offline)
    return () => { window.removeEventListener('online', online); window.removeEventListener('offline', offline); if (watchId.current !== null) navigator.geolocation.clearWatch(watchId.current) }
  }, [flushQueue])

  const sendPoint = useCallback(async (position: GeolocationPosition) => {
    if (!activeTrip) return
    const coordinates: [number, number] = [position.coords.latitude, position.coords.longitude]
    setCurrentPosition(coordinates); setAccuracy(position.coords.accuracy)
    const now = Date.now(); const speed = position.coords.speed || 0; const moving = speed >= 1.4
    const minimumTime = (moving ? activeTrip.settings.update_interval_seconds : activeTrip.settings.stationary_interval_seconds) * 1000
    const moved = lastSent.current ? distanceMeters(lastSent.current.coordinates, coordinates) : Infinity
    const headingChanged = lastSent.current?.heading !== null && position.coords.heading !== null && Math.abs((lastSent.current?.heading || 0) - position.coords.heading) >= 20
    if (lastSent.current && now - lastSent.current.at < minimumTime && moved < activeTrip.settings.minimum_movement_meters && !headingChanged) return
    const battery = await (navigator as BatteryNavigator).getBattery?.().catch(() => null)
    const point: LocationSubmission = { idempotency_key: crypto.randomUUID(), latitude: coordinates[0], longitude: coordinates[1], accuracy_meters: position.coords.accuracy, altitude: position.coords.altitude, altitude_accuracy: position.coords.altitudeAccuracy, heading_degrees: position.coords.heading, speed_mps: position.coords.speed, captured_at: new Date(position.timestamp).toISOString(), battery_percentage: battery ? Math.round(battery.level * 100) : null, network_state: navigator.onLine ? 'online' : 'offline' }
    lastSent.current = { at: now, coordinates, heading: position.coords.heading }
    if (!navigator.onLine) { await queueLocation(point); await refreshQueueCount(); return }
    try { await api.post('/tracking/locations', point); await flushQueue() }
    catch { await queueLocation(point); await refreshQueueCount() }
  }, [activeTrip, flushQueue, refreshQueueCount])

  const beginWatch = useCallback(() => {
    if (!navigator.geolocation) { setPermission('unavailable'); setMessage('This browser does not provide the Geolocation API.'); return }
    setPermission('requesting')
    watchId.current = navigator.geolocation.watchPosition((position) => { setPermission('granted'); sendPoint(position) }, (error) => { setPermission(error.code === error.PERMISSION_DENIED ? 'denied' : 'unavailable'); setMessage(error.code === error.PERMISSION_DENIED ? 'Location permission was denied. Enable it in browser settings to track this trip.' : `GPS unavailable: ${error.message}`) }, { enableHighAccuracy: true, maximumAge: 3_000, timeout: 15_000 })
  }, [sendPoint])

  const resumeGps = () => {
    if (watchId.current !== null) navigator.geolocation.clearWatch(watchId.current)
    watchId.current = null
    beginWatch()
    setMessage('GPS updates resumed for the active tracking session.')
  }

  const start = async () => {
    try {
      if (!navigator.geolocation) throw new Error('This browser does not provide the Geolocation API.')
      setPermission('requesting')
      const initialPosition = await new Promise<GeolocationPosition>((resolve, reject) => navigator.geolocation.getCurrentPosition(resolve, reject, { enableHighAccuracy: true, maximumAge: 0, timeout: 15_000 }))
      setPermission('granted')
      const result = await api.post('/tracking/sessions/start', { consent: true, consent_version: '2026-07' })
      setActiveTrip((current) => current ? { ...current, tracking_session: result.data, trip: { ...current.trip, status: 'In Progress' } } : current)
      setTrackingStatus('ACTIVE'); setMessage('Location sharing is active for this trip.'); await sendPoint(initialPosition); beginWatch()
    } catch (reason) { const geoError = reason as Partial<GeolocationPositionError>; setPermission(geoError.code === 1 ? 'denied' : 'idle'); setMessage(geoError.message || messageFrom(reason)) }
  }
  const pause = async () => {
    if (!activeTrip?.tracking_session) return
    try { await api.post(`/tracking/sessions/${activeTrip.tracking_session.id}/pause`); if (watchId.current !== null) navigator.geolocation.clearWatch(watchId.current); watchId.current = null; setTrackingStatus('PAUSED'); setMessage('Tracking paused by driver.') } catch (reason) { setMessage(messageFrom(reason)) }
  }
  const resume = async () => {
    if (!activeTrip?.tracking_session) return
    try { await api.post(`/tracking/sessions/${activeTrip.tracking_session.id}/resume`); setTrackingStatus('ACTIVE'); beginWatch(); setMessage('Tracking resumed.') } catch (reason) { setMessage(messageFrom(reason)) }
  }
  const end = async () => {
    if (!activeTrip?.tracking_session) return
    try { await api.post(`/tracking/sessions/${activeTrip.tracking_session.id}/end`); if (watchId.current !== null) navigator.geolocation.clearWatch(watchId.current); watchId.current = null; setTrackingStatus('ENDED'); setMessage('Location sharing ended. The trip remains active.') } catch (reason) { setMessage(messageFrom(reason)) }
  }
  const complete = async () => {
    if (!activeTrip) return
    try { await api.post(`/trips/${activeTrip.trip.id}/complete`); if (watchId.current !== null) navigator.geolocation.clearWatch(watchId.current); setTrackingStatus('ENDED'); setMessage('Trip completed. Tracking stopped and resources were released.'); setActiveTrip(null) } catch (reason) { setMessage(messageFrom(reason)) }
  }
  const reportIssue = async () => {
    try { await api.post('/tracking/issues', { issue_type: 'DRIVER_EMERGENCY', message: 'Driver requested operational assistance from the live trip page.' }); setMessage('Issue reported to fleet operations.') } catch (reason) { setMessage(messageFrom(reason)) }
  }

  if (!activeTrip) return <section className="driver-tracking-empty"><Navigation size={38}/><h1>No active trip</h1><p>{message || 'A dispatched trip assigned to your driver profile will appear here.'}</p></section>
  const ownVehicle = visibleFleet.find((vehicle) => vehicle.vehicle_id === activeTrip.vehicle.id)
  const mapFleet = currentPosition ? visibleFleet.map((vehicle) => vehicle.vehicle_id === activeTrip.vehicle.id ? { ...vehicle, latitude: currentPosition[0], longitude: currentPosition[1], accuracy_meters: accuracy, freshness_status: 'ONLINE' as const } : vehicle) : visibleFleet

  return <div className="driver-live-page">
    <section className="driver-trip-hero"><div><p className="eyebrow">MY LIVE TRIP</p><h1>{activeTrip.trip.source} <span>→</span> {activeTrip.trip.destination}</h1><p>{activeTrip.trip.id} · {activeTrip.vehicle.name} · {activeTrip.vehicle.registration}</p></div><div className={`tracking-indicator tracking-${trackingStatus.toLowerCase()}`}><Radio size={18}/><span><b>{trackingStatus.replace('_', ' ')}</b><small>{permission === 'granted' ? 'High-accuracy GPS enabled' : `GPS ${permission}`}</small></span></div></section>
    {message && <div className="notice driver-notice">{message}</div>}
    <section className="driver-status-strip"><article><MapPin/><div><span>GPS accuracy</span><b>{accuracy !== null ? `±${Math.round(accuracy)} m` : 'Awaiting GPS'}</b></div></article><article><Signal/><div><span>Network</span><b>{networkOnline ? 'Online' : 'Offline'}</b></div></article><article><Radio/><div><span>Queued points</span><b>{offlineCount}</b></div></article><article><Navigation/><div><span>Distance remaining</span><b>{ownVehicle?.remaining_distance_km !== null && ownVehicle?.remaining_distance_km !== undefined ? `~${ownVehicle.remaining_distance_km} km` : 'Calculating'}</b></div></article></section>
    <section className="driver-map-card"><FleetTrackingMap vehicles={mapFleet} selectedVehicleId={activeTrip.vehicle.id} onSelect={() => {}} autoFollow fitRequest={fitRequest} routeCoordinates={routeCoordinates} provider={activeTrip.settings.map_provider}/><button className="driver-recenter" onClick={() => setFitRequest((value) => value + 1)}><Navigation size={16}/> Recenter route</button></section>
    <section className="driver-controls-card"><div><h2>Location sharing</h2><p>Tracking is limited to this active trip. A visible indicator remains on while GPS updates are being collected.</p></div><div className="driver-controls">
      {(trackingStatus === 'NOT_STARTED' || trackingStatus === 'ENDED') && <button className="primary" onClick={start}><Play size={18}/> Start tracking</button>}
      {trackingStatus === 'ACTIVE' && permission !== 'granted' && <button className="primary" onClick={resumeGps}><Navigation size={18}/> Resume GPS</button>}
      {trackingStatus === 'ACTIVE' && activeTrip.settings.allow_pause && <button className="secondary" onClick={pause}><Pause size={18}/> Pause</button>}
      {trackingStatus === 'PAUSED' && <button className="primary" onClick={resume}><Play size={18}/> Resume</button>}
      {(trackingStatus === 'ACTIVE' || trackingStatus === 'PAUSED') && <button className="secondary danger-outline" onClick={end}><Square size={17}/> End tracking</button>}
      <button className="secondary emergency-button" onClick={reportIssue}><AlertOctagon size={18}/> Report issue</button>
      <button className="primary complete-trip" onClick={complete}><CheckCircle2 size={18}/> Complete trip</button>
    </div></section>
    <p className="driver-background-note">Keep this page open while driving. Browser GPS may pause when the phone is locked, battery saving is active, or the operating system suspends the browser.</p>
  </div>
}
