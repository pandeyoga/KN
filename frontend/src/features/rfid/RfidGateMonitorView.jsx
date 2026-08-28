import { useEffect, useRef, useState } from "react";
import { Cpu, RefreshCw, ScanLine, ShieldCheck, ShieldAlert, ArrowLeftRight, Radio } from "lucide-react";
import KNSelect from "../../components/KNSelect";
import ErrorNotice from "../../components/ErrorNotice";
import axios, { API } from "../../services/apiClient";
import { Stat, EmptyBox, Pill, SectionCard, RfidHeader, TabBtn, fmtTime, resultColor, useWarehouses } from "./rfidShared";
import RfidSecurityPanel from "./RfidSecurityPanel";

export default function RfidGateMonitorView({ currentUser, selectedEntity }) {
  const { whId, setWhId, whOpts } = useWarehouses();
  const [devices, setDevices] = useState([]);
  const [gateId, setGateId] = useState("");
  const [tags, setTags] = useState([]);
  const [rollId, setRollId] = useState("");
  const [reads, setReads] = useState([]);
  const [summary, setSummary] = useState(null);
  const [lastResult, setLastResult] = useState(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const [tab, setTab] = useState("monitor");
  const [live, setLive] = useState(false);
  const liveT = useRef(null);

  const loadReads = async () => {
    try {
      const params = whId ? { warehouse_id: whId } : {};
      const [r, s] = await Promise.all([
        axios.get(`${API}/rfid/reads`, { params: { ...params, limit: 25 } }),
        axios.get(`${API}/rfid/summary`, { params }),
      ]);
      setReads((r.data.reads || []).filter((x) => x.read_type !== "inventory"));
      setSummary(s.data);
    } catch { /* polling senyap */ }
  };

  useEffect(() => {
    if (live) { liveT.current = setInterval(loadReads, 4000); }
    return () => { if (liveT.current) clearInterval(liveT.current); };
  }, [live, whId]); // eslint-disable-line

  const load = async () => {
    setLoading(true); setError(null);
    try {
      const params = whId ? { warehouse_id: whId } : {};
      const [d, t, r, s] = await Promise.all([
        axios.get(`${API}/rfid/devices`, { params }),
        axios.get(`${API}/rfid/tags`, { params: { ...params, status: "active" } }),
        axios.get(`${API}/rfid/reads`, { params: { ...params, limit: 25 } }),
        axios.get(`${API}/rfid/summary`, { params }),
      ]);
      const gates = (d.data.devices || []).filter((x) => x.type === "gate");
      setDevices(gates); setTags(t.data.tags || []); setSummary(s.data);
      setReads((r.data.reads || []).filter((x) => x.read_type !== "inventory"));
      if (gates.length && !gates.find((g) => g.id === gateId)) setGateId(gates[0].id);
    } catch (e) { setError(e.response?.data?.detail || e.message || "Gagal memuat gate monitor"); }
    finally { setLoading(false); }
  };
  useEffect(() => { load(); }, [whId, selectedEntity]); // eslint-disable-line

  const simulate = async () => {
    if (!gateId || !rollId) { setError("Pilih gate & roll dulu"); return; }
    setBusy(true); setError(null); setLastResult(null);
    try {
      const r = await axios.post(`${API}/rfid/gate/simulate`, { device_id: gateId, roll_id: rollId });
      setLastResult(r.data);
      await load();
    } catch (e) { setError(e.response?.data?.detail || "Gagal simulasi gate"); } finally { setBusy(false); }
  };

  const gateOpts = devices.map((d) => ({ value: d.id, label: `${d.code} · ${d.direction === "in" ? "MASUK" : "KELUAR"} · ${d.warehouse_name || ""}` }));
  const rollOpts = tags.map((t) => ({ value: t.roll_id, label: `${t.roll_no} · ${t.sku || "—"} · ${t.epc}` }));
  const gate = devices.find((d) => d.id === gateId);

  return (
    <div data-testid="rfid-gate-view" className="space-y-4">
      <RfidHeader icon={Cpu} title="Gate Monitor" subtitle="Simulasikan pembacaan tag di gate. Sistem memvalidasi HIJAU (sah) / MERAH (tak sah).">
        <KNSelect data-testid="rfid-gate-wh" value={whId} onValueChange={setWhId} options={whOpts}
          className="field !py-1 !px-2 text-[12px] w-auto" placeholder="Gudang" />
        <button data-testid="rfid-gate-live" onClick={() => setLive((v) => !v)}
          className={`flex items-center gap-1 rounded-lg px-3 py-1.5 text-[12px] font-semibold ${
            live ? "bg-[#C0341D] text-white" : "border border-[#EFF0F2] bg-white hover:bg-[#F5F5F7]"}`}>
          <Radio size={14} className={live ? "animate-pulse" : ""} /> {live ? "LIVE ●" : "Mode Live"}
        </button>
        <button data-testid="rfid-gate-refresh" onClick={load}
          className="flex items-center gap-1 rounded-lg border border-[#EFF0F2] bg-white px-3 py-1.5 text-[12px] font-semibold hover:bg-[#F5F5F7]">
          <RefreshCw size={14} className={loading ? "animate-spin" : ""} /> Refresh
        </button>
      </RfidHeader>

      {error && <ErrorNotice message={error} onRetry={load} />}

      <div className="flex gap-1 border-b border-[#EFF0F2]">
        <TabBtn id="monitor" tab={tab} setTab={setTab} label="Monitor Gate" testId="gate-tab-monitor" />
        <TabBtn id="security" tab={tab} setTab={setTab} label="Alarm & Keamanan" testId="gate-tab-security" />
      </div>

      {tab === "security" ? (
        <RfidSecurityPanel whId={whId} selectedEntity={selectedEntity} />
      ) : (
      <>
      {live && (() => {
        const gateReads = gateId ? reads.filter((r) => r.device_id === gateId) : reads;
        const last = gateReads[0];
        const bg = !last ? "#F5F5F7" : last.result === "green" ? "#1B7F4B" : last.result === "red" ? "#C0341D" : "#0058CC";
        return (
          <div data-testid="rfid-gate-kiosk" className="rounded-2xl p-6 text-center transition-colors"
            style={{ background: bg, color: last ? "#fff" : "#6B6B73" }}>
            {!last ? (
              <p className="text-[16px] font-bold">Menunggu pembacaan gate… (layar admin gudang — update tiap 4 detik)</p>
            ) : (
              <>
                <p className="text-4xl sm:text-5xl font-black tracking-wide" data-testid="rfid-kiosk-verdict">
                  {last.result === "green" ? "✓ HIJAU — LOLOS" : last.result === "red" ? "✕ MERAH — TAHAN" : "INFO"}
                </p>
                <p className="mt-2 text-[15px] font-semibold">{last.roll_no || last.epc} · {last.product_name || "EPC tak dikenal"}</p>
                <p className="text-[13px] opacity-90">{last.reason}</p>
                <p className="mt-1 text-[11px] opacity-75">{last.device_name} · {fmtTime(last.timestamp)}</p>
              </>
            )}
          </div>
        );
      })()}

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <Stat icon={ArrowLeftRight} label="Gate Aktif" value={devices.filter((d) => d.status === "online").length} color="#0058CC" loading={loading} />
        <Stat icon={ScanLine} label="Baca Hari Ini" value={summary?.reads_today ?? 0} color="#5856D6" loading={loading} />
        <Stat icon={ShieldAlert} label="Alert (Merah) Hari Ini" value={summary?.alerts_today ?? 0} color="#C0341D" loading={loading} testId="rfid-gate-alerts" />
        <Stat icon={ShieldCheck} label="Tag Aktif" value={summary?.tags_active ?? 0} color="#34C759" loading={loading} />
      </div>

      <SectionCard title="Simulasi Pembacaan Gate">
        {devices.length === 0 ? (
          <EmptyBox icon={Cpu} text="Belum ada gate di gudang ini. Buat gate di menu Devices dulu." />
        ) : (
          <div className="space-y-3">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              <div><label className="text-[11px] text-[#6B6B73]">Gate</label>
                <KNSelect data-testid="rfid-gate-select" value={gateId} onValueChange={setGateId} options={gateOpts} className="field mt-1 text-[12px]" placeholder="Pilih gate" /></div>
              <div><label className="text-[11px] text-[#6B6B73]">Roll (tag) yang lewat</label>
                <KNSelect data-testid="rfid-gate-roll" value={rollId} onValueChange={setRollId} options={rollOpts} className="field mt-1 text-[12px]" placeholder="Pilih roll ber-tag" searchable /></div>
            </div>
            {gate && gate.status !== "online" && <p className="text-[11px] text-[#C0341D]">Gate ini OFFLINE — nyalakan di menu Devices.</p>}
            <button data-testid="rfid-gate-simulate" disabled={busy || !gateId || !rollId} onClick={simulate}
              className="flex items-center gap-2 rounded-lg bg-[#0058CC] text-white px-4 py-2 text-[13px] font-semibold disabled:opacity-40">
              <ScanLine size={16} /> Baca di Gate
            </button>

            {lastResult && (
              <div data-testid="rfid-gate-result" className="rounded-xl p-4 flex items-center gap-3"
                style={{ background: lastResult.result === "green" ? "#E7F7EC" : lastResult.result === "red" ? "#FBE9E7" : "#EAF2FF" }}>
                {lastResult.result === "green" ? <ShieldCheck size={28} className="text-[#1B7E3B]" />
                  : lastResult.result === "red" ? <ShieldAlert size={28} className="text-[#C0341D]" />
                    : <ScanLine size={28} className="text-[#0058CC]" />}
                <div>
                  <p className="text-[15px] font-bold" style={{ color: lastResult.result === "green" ? "#1B7E3B" : lastResult.result === "red" ? "#C0341D" : "#0058CC" }}>
                    {lastResult.result === "green" ? "HIJAU — LOLOS" : lastResult.result === "red" ? "MERAH — DITAHAN" : "INFO"}
                  </p>
                  <p className="text-[12px] text-[#3A3A3C]">{lastResult.reason}</p>
                  <p className="text-[10px] text-[#6B6B73] mt-0.5">{lastResult.roll_no} · {lastResult.product_name} · {fmtTime(lastResult.timestamp)}</p>
                </div>
              </div>
            )}
          </div>
        )}
      </SectionCard>

      <SectionCard title="Aktivitas Gate Terbaru">
        {loading ? <div className="h-16 bg-[#F5F5F7] rounded animate-pulse" />
          : reads.length === 0 ? <EmptyBox icon={ScanLine} text="Belum ada aktivitas gate. Lakukan simulasi di atas." />
            : (
              <div className="space-y-1.5">
                {reads.map((r) => (
                  <div key={r.id} data-testid={`rfid-read-${r.id}`} className="flex items-center gap-2 rounded-lg bg-[#FAFAFB] px-3 py-2">
                    <Pill color={resultColor(r.result)}>{r.result === "green" ? "LOLOS" : r.result === "red" ? "DITAHAN" : "INFO"}</Pill>
                    <span className="text-[12px] font-semibold">{r.roll_no || "—"}</span>
                    <span className="text-[11px] text-[#6B6B73]">{r.product_name} · {r.read_type} @ {r.device_name}</span>
                    <span className="ml-auto text-[10px] text-[#8E8E93]">{fmtTime(r.timestamp)}</span>
                  </div>
                ))}
              </div>
            )}
      </SectionCard>
      </>
      )}
    </div>
  );
}
