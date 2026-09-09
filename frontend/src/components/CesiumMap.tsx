import { useEffect, useRef } from "react";
import * as Cesium from "cesium";
import "cesium/Build/Cesium/Widgets/widgets.css";
import type { Parcel, Property, Region } from "../lib/types";

// OSM basemap => no Ion token required.
const OSM_URL = "https://tile.openstreetmap.org/";

export interface LayerState {
  parcels: boolean;
  buildings: boolean;
  properties: boolean;
  underground: boolean;
  conflicts: boolean;
}

interface Props {
  parcels: Parcel[];
  buildings: Property[];
  volumes: Property[]; // volumes + underground + basement + parking
  conflictIds: string[];
  layers: LayerState;
  floors: Property[];
  explode: boolean;
  undergroundRaised: boolean;
  region: Region | null;
  revision: number;
  onPick: (kind: "parcel" | "property", id: string) => void;
}

function ring2d(gj: { coordinates: number[][][] }): number[][] {
  return gj.coordinates[0] || [];
}

function baseColor(p: Property, inConflict: boolean): [number, number, number, number] {
  if (inConflict) return [220, 38, 38, 0.7];
  if (p.source_type === "ai_derived") return [168, 85, 247, 0.7]; // purple
  switch (p.status) {
    case "approved":
    case "verified":
      return [16, 160, 133, 0.72];
    case "submitted":
      return [2, 132, 199, 0.7];
    case "pending_verification":
      return [245, 158, 11, 0.75];
    case "rejected":
      return [225, 29, 72, 0.7];
    default:
      return [100, 116, 139, 0.6];
  }
}

export default function CesiumMap(props: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const viewerRef = useRef<any>(null);
  const handlersRef = useRef<{
    onPick: Props["onPick"];
  }>({ onPick: props.onPick });
  handlersRef.current.onPick = props.onPick;

  // ---- init once ----
  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    let viewer: any;
    try {
      const opts: any = {
        animation: false,
        timeline: false,
        baseLayerPicker: false,
        geocoder: false,
        homeButton: true,
        navigationHelpButton: false,
        sceneModePicker: false,
        fullscreenButton: false,
        infoBox: false,
        selectionIndicator: true,
        requestRenderMode: false,
      };
      try {
        const osm = new Cesium.OpenStreetMapImageryProvider({ url: OSM_URL });
        // modern Cesium expects an ImageryLayer for the baseLayer option
        opts.baseLayer = new Cesium.ImageryLayer(osm);
      } catch {
        opts.imageryProvider = new Cesium.OpenStreetMapImageryProvider({ url: OSM_URL });
      }
      viewer = new Cesium.Viewer(el, opts);
      viewer.scene.globe.depthTestAgainstTerrain = false;
      viewer.camera.flyTo({
        destination: Cesium.Cartesian3.fromDegrees(78.9629, 20.5937, 2200000),
      });
      const handler = new Cesium.ScreenSpaceEventHandler(viewer.scene.canvas);
      handler.setInputAction((click: any) => {
        const picked = viewer.scene.pick(click.position);
        if (picked && picked.id && typeof picked.id === "string") {
          const raw: string = picked.id;
          if (raw.startsWith("parcel:")) {
            handlersRef.current.onPick("parcel", raw.slice("parcel:".length));
          } else if (raw.startsWith("prop:")) {
            handlersRef.current.onPick("property", raw.slice("prop:".length));
          }
        }
      }, Cesium.ScreenSpaceEventType.LEFT_CLICK);
      viewerRef.current = viewer;
    } catch (err) {
      // WebGL / Cesium unavailable -> fallback message stays visible
      el.innerHTML =
        '<div class="grid h-full place-items-center text-slate-500 text-sm p-6">' +
        "3D globe unavailable in this browser. API & data remain usable.</div>";
      console.error("Cesium init failed", err);
    }
    return () => {
      try {
        if (viewerRef.current) viewerRef.current.destroy();
      } catch {
        /* ignore */
      }
      viewerRef.current = null;
    };
  }, []);

  // ---- (re)build entities ----
  useEffect(() => {
    const viewer = viewerRef.current;
    if (!viewer) return;
    try {
      viewer.entities.removeAll();
    } catch {
      return;
    }
    const conflictSet = new Set(props.conflictIds);
    const addPolygon = (entity: any) => {
      try {
        viewer.entities.add(entity);
      } catch {
        /* skip malformed */
      }
    };

    // parcels
    if (props.layers.parcels) {
      props.parcels.forEach((par) => {
        const ring = ring2d(par.footprint_geojson);
        if (!ring || ring.length < 4) return;
        addPolygon({
          id: "parcel:" + par.id,
          polygon: {
            hierarchy: new Cesium.PolygonHierarchy(Cesium.Cartesian3.fromDegreesArray(ring.flat())),
            material: Cesium.Color.fromBytes(250, 204, 21, 90),
            outline: true,
            outlineColor: Cesium.Color.fromBytes(133, 104, 6, 255),
            height: 0,
          },
        });
      });
    }

    // buildings
    if (props.layers.buildings) {
      props.buildings.forEach((b) => {
        const ring = ring2d(b.footprint_geojson);
        if (!ring || ring.length < 4) return;
        const zmax = (b.zmax ?? 0) > 0 ? b.zmax! : 1;
        const [r, g, bl, a] = baseColor(b, conflictSet.has(b.id));
        addPolygon({
          id: "prop:" + b.id,
          polygon: {
            hierarchy: new Cesium.PolygonHierarchy(Cesium.Cartesian3.fromDegreesArray(ring.flat())),
            material: Cesium.Color.fromBytes(r, g, bl, Math.round(a * 255)),
            outline: true,
            outlineColor: Cesium.Color.fromBytes(r, g, bl, 255),
            height: 0,
            extrudedHeight: zmax,
          },
        });
      });
    }

    // volumes + underground
    if (props.layers.properties) {
      props.volumes.forEach((v) => {
        const ring = ring2d(v.footprint_geojson);
        if (!ring || ring.length < 4) return;
        const underground = (v.zmin ?? 0) < 0;
        const kind = v.property_type;
        const isUndergroundKind = ["underground_asset", "basement", "parking"].includes(kind);
        if (isUndergroundKind && !props.layers.underground) return;
        if (underground && !props.undergroundRaised) return;
        const base = underground ? -1 * (v.zmin ?? 0) : 0; // raise below-ground for viewing
        const zminD = (v.zmin ?? 0) + base;
        const zmaxD = Math.max((v.zmax ?? 0) + base, zminD + 0.5);
        const [r, g, bl, a] = underground
          ? [30, 64, 175, 0.7]
          : conflictSet.has(v.id)
          ? [220, 38, 38, 0.7]
          : [245, 158, 11, 0.6];
        addPolygon({
          id: "prop:" + v.id,
          polygon: {
            hierarchy: new Cesium.PolygonHierarchy(Cesium.Cartesian3.fromDegreesArray(ring.flat())),
            material: Cesium.Color.fromBytes(r, g, bl, Math.round(a * 255)),
            outline: true,
            outlineColor: Cesium.Color.fromBytes(r, g, bl, 255),
            height: Math.max(0, zminD),
            extrudedHeight: Math.max(0, zmaxD),
          },
        });
      });
    }

    // selected building floors (+explode)
    if (props.floors.length > 0) {
      const sorted = [...props.floors].sort((a, b) => (a.zmin ?? 0) - (b.zmin ?? 0));
      const gap = props.explode ? 6 : 0;
      sorted.forEach((f, i) => {
        const ring = ring2d(f.footprint_geojson);
        if (!ring || ring.length < 4) return;
        const off = i * gap;
        const lo = (f.zmin ?? 0) + off;
        const hi = Math.max((f.zmax ?? 0) + off, lo + 0.5);
        const [r, g, bl] = baseColor(f, false);
        addPolygon({
          id: "prop:" + f.id,
          polygon: {
            hierarchy: new Cesium.PolygonHierarchy(Cesium.Cartesian3.fromDegreesArray(ring.flat())),
            material: Cesium.Color.fromBytes(r, g, bl, 160),
            outline: true,
            outlineColor: Cesium.Color.fromBytes(255, 255, 255, 160),
            height: lo,
            extrudedHeight: hi,
          },
        });
      });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [
    props.revision,
    props.layers.parcels,
    props.layers.buildings,
    props.layers.properties,
    props.layers.underground,
    props.layers.conflicts,
    props.explode,
    props.undergroundRaised,
    props.floors,
    props.parcels,
    props.buildings,
    props.volumes,
    props.conflictIds,
  ]);

  // fly to region
  useEffect(() => {
    const viewer = viewerRef.current;
    if (!viewer || !props.region) return;
    const { lon, lat } = props.region.center;
    let altitude = 90000;
    if (props.region.kind === "state") altitude = 700000;
    if (props.region.kind === "country") altitude = 2200000;
    if (props.region.kind === "pilot") altitude = 1800;
    try {
      viewer.camera.flyTo({
        destination: Cesium.Cartesian3.fromDegrees(lon, lat, altitude),
      });
    } catch {
      /* ignore */
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [props.region]);

  return (
    <div className="relative h-full w-full overflow-hidden">
      <div ref={containerRef} className="h-full w-full" />
      {props.layers.underground && (
        <div className="pointer-events-none absolute left-1/2 top-2 -translate-x-1/2 rounded bg-slate-900/80 px-3 py-1 text-xs text-emerald-300">
          Underground layer — objects below ground are raised for viewing
        </div>
      )}
    </div>
  );
}
