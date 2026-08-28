# Analisis Mendalam WMS & RFID — Kain Nusantara (Juni 2026)

## A. Kondisi Saat Ini (Hasil Audit Kode)

### RFID (Fase 5 — masih SIMULATOR)
- `rfid_tags`: encode tag↔roll (EPC auto-generate), auto-encode massal, retire tag. Roll-as-SSOT (RFID tidak mengubah kuantitas stok).
- `rfid_devices`: 3 tipe (gate in/out, fixed_reader, handheld) per gudang + seed default. Status online/offline manual, heartbeat hanya di-set saat edit.
- `rfid_reads`: log event. Keputusan gate HIJAU/MERAH murni berbasis STATUS roll (available/quarantine = merah keluar; reserved/allocated = hijau keluar).
- Gate Monitor UI: SIMULASI manual (pilih gate, pilih 1 roll, klik tombol). Bukan layar live.
- Reader scan: sweep simulasi (baca SEMUA tag aktif di gudang), bukan sesi validasi.
- Lokasi RFID: deteksi drift (last-seen gudang ≠ gudang roll).

### WMS
- Inbound: task dari PO → scan-receive (input manual qty/batch/lot/grade, catch-weight, konversi UOM), eskalasi, complete.
- Outbound: task dari SO → release, scan-pick, eskalasi, dispatch + surat jalan. HANYA dari SO (sudah sesuai prinsip Anda).
- Putaway: antrean roll tanpa bin → tempatkan ke bin. Validasi: bin ada di gudang yg sama + pagar tahanan inspeksi (hold QC). Struktur Zone→Rack→Level→Bin embedded di `warehouses.zones`, ada kapasitas & utilisasi bin.
- Lain: QC inspeksi roll, grading, cycle count, transfer antar-gudang, lot genealogy.

## B. GAP vs Kebutuhan Anda (printer + 2 gate + handheld, keamanan penuh)

| # | Kebutuhan Anda | Kondisi Sekarang | Gap |
|---|---|---|---|
| 1 | Penerimaan barang → BULK PRINT tag RFID dari pembelian (PO) | Encode per-roll / auto-encode simulasi. TIDAK ada integrasi printer RFID (ZPL/Zebra), tidak ada "print job" per GR/PO | **BESAR** — perlu modul Print Job: pilih PO/GR → generate EPC batch → kirim ZPL ke printer → status printed/encoded |
| 2 | Validasi hasil print dengan HANDHELD | Reader scan = sweep simulasi semua tag. Tidak ada sesi verifikasi "expected vs actual" | **BESAR** — perlu Sesi Verifikasi: daftar EPC yang diharapkan (dari print job/GR) vs yang terbaca handheld, selisih di-highlight |
| 3 | Putaway dengan RULES per gudang (kategori/jenis kain) | Gudang TIDAK punya field rules. Putaway hanya cek bin ada + hold QC | **BESAR** — perlu `warehouses.storage_rules` (kategori/jenis kain yang diizinkan, per gudang / per zona) + enforcement di `putaway_roll` |
| 4 | Gate IN validasi barang masuk sesuai tujuan putaway/rules gudang | Keputusan gate hanya berbasis status roll, tidak melihat gudang tujuan / rules / dokumen | **BESAR** — gate IN harus cek: roll ini memang ditujukan ke gudang ini (dari GR/putaway/transfer)? Kategorinya cocok dengan rules gudang? |
| 5 | Barang keluar HANYA dari SO, gate OUT validasi | Sebagian ada (status reserved/allocated = hijau) tapi TIDAK terikat dokumen: tidak ada manifest "gate-out session untuk SO-123, roll yang sah = X,Y,Z" | **SEDANG** — perlu Gate Manifest per SO/dispatch: roll di luar manifest = MERAH + alarm, walau statusnya allocated untuk SO lain |
| 6 | Layar admin gudang di gate IN & OUT per gudang | Gate Monitor = form simulasi, bukan kiosk live | **BESAR** — perlu Layar Gate (kiosk mode): feed real-time (polling/WebSocket), lampu HIJAU/MERAH besar, antrean dokumen aktif, tombol acknowledge alarm |
| 7 | Integrasi hardware nyata (fixed gate, handheld, printer) | 100% simulator. Tidak ada endpoint ingest untuk device fisik, tidak ada API key device, tidak ada heartbeat | **BESAR** — perlu Device Ingest API: `POST /api/rfid/ingest` (device_key + list EPC terbaca), heartbeat, antifraud (device hanya boleh lapor untuk gudangnya) |
| 8 | Keamanan penuh (anti-theft) | Read MERAH hanya tercatat di log | **SEDANG** — perlu Incident/Alarm workflow: alarm → acknowledge oleh admin gudang → catatan tindakan → laporan shrinkage |
| 9 | (Bonus standar industri) Cycle count via RFID | Cycle count ada tapi manual, tidak pakai sweep RFID | **KECIL** — rekonsiliasi hasil sweep handheld vs stok sistem |

## C. Perbandingan dengan Cleverence Warehouse 15

Cleverence W15 (standar industri): hybrid barcode+RFID, bulk read 200 item/3 detik, dock-gate & shrinkage control, receiving tervalidasi vs PO real-time, putaway dengan zone/category rules + rekomendasi lokasi, picking terpandu per dokumen, stock-taking full/parsial via RFID, print label on-the-spot (Bluetooth/WiFi), offline-first, hardware-agnostic (Zebra/Honeywell/Chainway), open API.

Posisi Kain Nusantara:
- ✅ SETARA/di atas: struktur lokasi 4 level, SSOT roll, pagar QC hold, lot genealogy, multi-entity — Cleverence tidak sekaya ini di sisi ERP.
- ⚠️ SETARA sebagian: receiving vs PO (ada, tapi tanpa RFID), picking dari SO (ada, tanpa RFID).
- ❌ TERTINGGAL: semua yang menyentuh hardware nyata (print, ingest, gate live), putaway rules engine, sesi verifikasi expected-vs-actual, alarm workflow, mode offline handheld.

## D. Rekomendasi Arsitektur & Roadmap (menunggu persetujuan)

### Prinsip arsitektur
1. RFID tetap TIDAK mengubah kuantitas (Roll-as-SSOT dipertahankan) — RFID = mata & satpam, ERP = otak.
2. Semua alur diikat DOKUMEN: print job ← GR/PO, gate-out manifest ← SO/dispatch, gate-in expectation ← GR/putaway/transfer.
3. Device fisik bicara lewat satu pintu: `POST /api/rfid/ingest` dengan device API key (per device, per gudang). Simulator lama tetap ada untuk demo/testing.

### Roadmap bertahap
- **FASE R1 — Penerimaan & Printing**: koleksi `rfid_print_jobs` (dari GR/PO → generate EPC per roll → payload ZPL → status queued/printed/encoded/verified), UI "Cetak Tag Massal" di Inbound, endpoint download/kirim ZPL.
- **FASE R2 — Verifikasi Handheld**: `rfid_verify_sessions` (expected EPC list vs scanned), UI sesi verifikasi (progress %, missing/extra), handheld ingest endpoint.
- **FASE R3 — Putaway Rules Engine**: `warehouses.storage_rules` (kategori/jenis kain per gudang & per zona), enforcement di putaway + saran lokasi otomatis (rule-match + kapasitas tersisa).
- **FASE R4 — Gate Live & Manifest**: gate-in validation (dokumen + rules gudang), gate-out manifest per SO, `rfid_gate_sessions`, Layar Kiosk Gate per gudang (in & out) dengan feed real-time + alarm besar HIJAU/MERAH.
- **FASE R5 — Keamanan & Ops**: incident/alarm workflow (acknowledge, catatan, laporan shrinkage), heartbeat monitor device, cycle count via sweep RFID.

### Skema data baru (ringkas)
- `rfid_print_jobs`: {id, source_type: "gr"|"po", source_id, warehouse_id, items:[{roll_id, epc, zpl, status}], status, created_by}
- `rfid_verify_sessions`: {id, print_job_id|gr_id, expected_epcs[], scanned_epcs[], missing[], extra[], status}
- `warehouses.storage_rules`: {allowed_categories[], allowed_fabric_types[], zone_overrides:[{zone_id, allowed_categories[]}]}
- `rfid_gate_sessions`: {id, gate_id, direction, source_type: "so_dispatch"|"gr"|"transfer", source_id, manifest_epcs[], reads[], alarms[], status}
- `rfid_incidents`: {id, read_id, gate_id, severity, status: open|acknowledged|resolved, notes, actor}
