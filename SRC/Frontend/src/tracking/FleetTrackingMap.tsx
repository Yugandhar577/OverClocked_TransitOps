import { useEffect, useMemo, useRef } from 'react'
import L from 'leaflet'
import 'leaflet.markercluster'
import { Circle, MapContainer, Polyline, TileLayer, useMap } from 'react-leaflet'
import 'leaflet/dist/leaflet.css'
import 'leaflet.markercluster/dist/MarkerCluster.css'
import 'leaflet.markercluster/dist/MarkerCluster.Default.css'

import { resolveMapProvider } from './mapProvider'
import type { FleetVehicle, Geofence, LocationPoint } from './types'


type Props = {
  vehicles: FleetVehicle[]
  selectedVehicleId: string | null
  onSelect: (vehicleId: string) => void
  autoFollow: boolean
  fitRequest: number
  history?: LocationPoint[]
  geofences?: Geofence[]
  provider?: string
  routeCoordinates?: [number, number][]
}

const markerColor = (vehicle: FleetVehicle) => {
  if (vehicle.freshness_status === 'OFFLINE') return '#64748b'
  if (vehicle.freshness_status === 'STALE') return '#f59e0b'
  if (vehicle.movement_status === 'MOVING') return '#2563eb'
  return '#16a34a'
}

function MapController({ vehicles, selectedVehicleId, autoFollow, fitRequest }: Pick<Props, 'vehicles' | 'selectedVehicleId' | 'autoFollow' | 'fitRequest'>) {
  const map = useMap()
  const lastFitRequest = useRef(0)
  const selected = vehicles.find((vehicle) => vehicle.vehicle_id === selectedVehicleId)

  useEffect(() => {
    if (fitRequest === lastFitRequest.current) return
    lastFitRequest.current = fitRequest
    const points = vehicles.filter((vehicle) => vehicle.latitude !== null && vehicle.longitude !== null).map((vehicle) => [vehicle.latitude!, vehicle.longitude!] as [number, number])
    if (fitRequest > 0 && points.length) map.fitBounds(points, { padding: [45, 45], maxZoom: 13 })
  }, [fitRequest, map, vehicles])

  useEffect(() => {
    if (autoFollow && selected && selected.latitude !== null && selected.longitude !== null) map.setView([selected.latitude, selected.longitude], Math.max(map.getZoom(), 14), { animate: true })
  }, [autoFollow, map, selected])

  return null
}

function ClusteredVehicleMarkers({ vehicles, selectedVehicleId, onSelect }: Pick<Props, 'vehicles' | 'selectedVehicleId' | 'onSelect'>) {
  const map = useMap()

  useEffect(() => {
    const cluster = L.markerClusterGroup({ showCoverageOnHover: false, maxClusterRadius: 48, disableClusteringAtZoom: 15 })
    vehicles.forEach((vehicle) => {
      if (vehicle.latitude === null || vehicle.longitude === null) return
      const selected = selectedVehicleId === vehicle.vehicle_id
      const icon = L.divIcon({
        className: 'vehicle-marker-shell',
        html: `<span class="vehicle-map-marker${selected ? ' selected' : ''}" style="--marker-color:${markerColor(vehicle)}"><span>◆</span></span>`,
        iconSize: [selected ? 38 : 30, selected ? 38 : 30],
        iconAnchor: [selected ? 19 : 15, selected ? 19 : 15],
      })
      const marker = L.marker([vehicle.latitude, vehicle.longitude], { icon, title: vehicle.vehicle_name })
      const tooltip = document.createElement('div')
      const title = document.createElement('strong')
      title.textContent = vehicle.vehicle_name
      const details = document.createElement('span')
      details.textContent = `${vehicle.registration} · ${vehicle.freshness_status}`
      tooltip.append(title, document.createElement('br'), details)
      marker.bindTooltip(tooltip)
      marker.on('click', () => onSelect(vehicle.vehicle_id))
      cluster.addLayer(marker)
    })
    map.addLayer(cluster)
    return () => { map.removeLayer(cluster) }
  }, [map, onSelect, selectedVehicleId, vehicles])

  return null
}

export function FleetTrackingMap({ vehicles, selectedVehicleId, onSelect, autoFollow, fitRequest, history = [], geofences = [], provider, routeCoordinates = [] }: Props) {
  const mapProvider = useMemo(() => resolveMapProvider(provider), [provider])
  const selected = vehicles.find((vehicle) => vehicle.vehicle_id === selectedVehicleId)
  const historyLine = history.map((point) => [point.latitude, point.longitude] as [number, number])
  const routeLine = routeCoordinates.length ? routeCoordinates : selected?.source_coordinates && selected.destination_coordinates ? [selected.source_coordinates, selected.destination_coordinates] : []

  return <div className="tracking-map-wrap">
    {mapProvider.warning && <div className="map-provider-warning">{mapProvider.warning}</div>}
    <MapContainer center={[23.0225, 72.5714]} zoom={10} className="tracking-map" scrollWheelZoom>
      <TileLayer url={mapProvider.tileUrl} attribution={mapProvider.attribution}/>
      <MapController vehicles={vehicles} selectedVehicleId={selectedVehicleId} autoFollow={autoFollow} fitRequest={fitRequest}/>
      <ClusteredVehicleMarkers vehicles={vehicles} selectedVehicleId={selectedVehicleId} onSelect={onSelect}/>
      {historyLine.length > 1 && (
        <Polyline positions={historyLine} pathOptions={{ color: '#2563eb', weight: 4, opacity: .75 }}/>
      )}
      {routeLine.length > 1 && (
        <Polyline positions={routeLine} pathOptions={{ color: '#7c3aed', weight: 3, dashArray: '8 8', opacity: .7 }}/>
      )}
      {geofences.filter((fence) => fence.is_active).map((fence) => <Circle key={fence.id} center={[fence.center_latitude, fence.center_longitude]} radius={fence.radius_meters} pathOptions={{ color: fence.type === 'RESTRICTED' ? '#dc2626' : '#0f766e', fillOpacity: .08 }}/>) }
    </MapContainer>
  </div>
}
