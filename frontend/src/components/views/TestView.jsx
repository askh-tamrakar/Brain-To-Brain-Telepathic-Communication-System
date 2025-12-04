// import React, { useEffect, useRef, useState } from "react";

// const Card = ({ children, className = '' }) => (
//   <div className={`rounded-2xl shadow p-3 bg-white/5 ${className}`}>{children}</div>
// );
// const CardContent = ({ children }) => <div className="p-2">{children}</div>;
// const Button = ({ children, onClick, variant = 'default', className = '' }) => (
//   <button onClick={onClick} className={`px-3 py-1 rounded ${variant === 'ghost' ? 'bg-transparent' : 'bg-slate-700'} ${className}`}>{children}</button>
// );

// import { motion } from "framer-motion";
// import {
//   LineChart,
//   Line,
//   ResponsiveContainer,
//   XAxis,
//   YAxis,
//   Tooltip,
//   Legend,
// } from "recharts";

// // ----- CONFIG -----
// const DEFAULT_WS = (typeof process !== "undefined" && process?.env?.NEXT_PUBLIC_BCI_WS) ? process.env.NEXT_PUBLIC_BCI_WS : "ws://localhost:8000/ws";
// const SAMPLE_RATE = 250; // Hz (assumption) - adjust to your hardware
// const MAX_POINTS = 1024; // points kept per channel for plotting
// const EEG_CHANNELS = ["Fp1", "Fp2", "F7", "F8", "C3", "C4", "P3", "P4", "O1", "O2"];
// const EOG_CHANNELS = ["Left", "Right"];
// const EMG_CHANNELS = ["Arm", "Forearm"];

// // ----- Small Biquad implementation (RBJ cookbook) -----
// class Biquad {
//   constructor(type = "bandpass", fs = SAMPLE_RATE, f0 = 50, Q = 1) {
//     this.type = type;
//     this.fs = fs;
//     this.f0 = f0;
//     this.Q = Q;
//     this.x1 = 0; // previous input
//     this.x2 = 0; // input-2
//     this.y1 = 0; // previous output
//     this.y2 = 0; // output-2
//     this.updateCoeffs();
//   }

//   updateCoeffs() {
//     const omega = (2 * Math.PI * this.f0) / this.fs;
//     const alpha = Math.sin(omega) / (2 * this.Q);
//     const cosw = Math.cos(omega);
//     let b0, b1, b2, a0, a1, a2;

//     switch (this.type) {
//       case "notch":
//         b0 = 1; b1 = -2 * cosw; b2 = 1;
//         a0 = 1 + alpha; a1 = -2 * cosw; a2 = 1 - alpha;
//         break;
//       case "bandpass":
//         b0 = alpha; b1 = 0; b2 = -alpha;
//         a0 = 1 + alpha; a1 = -2 * cosw; a2 = 1 - alpha;
//         break;
//       default:
//         // bypass
//         b0 = 1; b1 = 0; b2 = 0; a0 = 1; a1 = 0; a2 = 0; break;
//     }

//     this.b0 = b0 / a0; this.b1 = b1 / a0; this.b2 = b2 / a0;
//     this.a1 = a1 / a0; this.a2 = a2 / a0;
//   }

//   setParams({ type, f0, Q, fs }) {
//     if (type) this.type = type;
//     if (f0) this.f0 = f0;
//     if (Q) this.Q = Q;
//     if (fs) this.fs = fs;
//     this.updateCoeffs();
//   }

//   processSample(x) {
//     // Direct Form 1 (using stored x1,x2,y1,y2 properly)
//     const y = this.b0 * x + this.b1 * this.x1 + this.b2 * this.x2 - this.a1 * this.y1 - this.a2 * this.y2;
//     this.x2 = this.x1;
//     this.x1 = x;
//     this.y2 = this.y1;
//     this.y1 = y;
//     return y;
//   }

//   processBlock(xs) {
//     return xs.map((v) => this.processSample(v));
//   }
// }

// // ----- Simple FFT (radix-2, iterative) -----
// function fft(re, im) {
//   const n = re.length;
//   if ((n & (n - 1)) !== 0) throw new Error("FFT size must be power of two");
//   let j = 0;
//   for (let i = 1; i < n - 1; i++) {
//     let bit = n >> 1;
//     while (j & bit) {
//       j ^= bit;
//       bit >>= 1;
//     }
//     j ^= bit;
//     if (i < j) {
//       [re[i], re[j]] = [re[j], re[i]];
//       [im[i], im[j]] = [im[j], im[i]];
//     }
//   }
//   for (let len = 2; len <= n; len <<= 1) {
//     const ang = (-2 * Math.PI) / len;
//     const wlen_r = Math.cos(ang);
//     const wlen_i = Math.sin(ang);
//     for (let i = 0; i < n; i += len) {
//       let wr = 1;
//       let wi = 0;
//       for (let k = 0; k < len / 2; k++) {
//         const u_r = re[i + k];
//         const u_i = im[i + k];
//         const v_r = re[i + k + len / 2] * wr - im[i + k + len / 2] * wi;
//         const v_i = re[i + k + len / 2] * wi + im[i + k + len / 2] * wr;
//         re[i + k] = u_r + v_r;
//         im[i + k] = u_i + v_i;
//         re[i + k + len / 2] = u_r - v_r;
//         im[i + k + len / 2] = u_i - v_i;
//         const tmp_r = wr * wlen_r - wi * wlen_i;
//         wi = wr * wlen_i + wi * wlen_r;
//         wr = tmp_r;
//       }
//     }
//   }
// }

// function computeMagnitudeSpectrum(samples) {
//   if (!samples || samples.length === 0) return [];
//   // Zero-pad to next power of two
//   let n = 1;
//   while (n < samples.length) n <<= 1;
//   const re = new Array(n).fill(0);
//   const im = new Array(n).fill(0);
//   for (let i = 0; i < samples.length; i++) re[i] = samples[i];
//   fft(re, im);
//   const mags = new Array(n / 2);
//   for (let i = 0; i < n / 2; i++) mags[i] = Math.sqrt(re[i] * re[i] + im[i] * im[i]) / n;
//   return mags;
// }

// // ----- Helper: downsample for plotting -----
// // returns array of objects { index, value } so Recharts XAxis can use 'index'
// function downsample(data, maxPoints) {
//   const arr = data || [];
//   if (arr.length <= maxPoints) return arr.map((d, i) => ({ index: i, value: d.value }));
//   const step = arr.length / maxPoints;
//   const out = [];
//   for (let i = 0; i < maxPoints; i++) {
//     const idx = Math.floor(i * step);
//     out.push({ index: i, value: arr[idx].value });
//   }
//   return out;
// }

// // ----- Main Component -----
// export default function TestView() {
//   const [wsUrl, setWsUrl] = useState(DEFAULT_WS);
//   const wsRef = useRef(null);
//   const [connected, setConnected] = useState(false);

//   // channel data store: { channelName: [{time, value}, ...] }
//   const [channels, setChannels] = useState(() => {
//     const m = {};
//     [...EEG_CHANNELS, ...EOG_CHANNELS, ...EMG_CHANNELS].forEach((c) => (m[c] = []));
//     return m;
//   });

//   const [selectedGroup, setSelectedGroup] = useState("EEG");
//   const [selectedChannels, setSelectedChannels] = useState(EEG_CHANNELS.slice(0, 3));

//   // filters
//   const [bandpassEnabled, setBandpassEnabled] = useState(false);
//   const [bpLow, setBpLow] = useState(1);
//   const [bpHigh, setBpHigh] = useState(40);
//   const [notchEnabled, setNotchEnabled] = useState(false);
//   const [notchFreq, setNotchFreq] = useState(50);

//   // biquad instances per channel (kept in ref so they're persistent between renders)
//   const filtersRef = useRef({});
//   useEffect(() => {
//     // (re)create filters when params change
//     Object.keys(filtersRef.current).forEach((ch) => {
//       const obj = filtersRef.current[ch];
//       if (!obj) return;
//       if (bandpassEnabled) obj.bandpass.setParams({ type: "bandpass", f0: (bpLow + bpHigh) / 2, Q: Math.max(0.1, (bpHigh - bpLow) / ((bpLow + bpHigh) / 2)) });
//       if (notchEnabled) obj.notch.setParams({ type: "notch", f0: notchFreq, Q: 30 });
//     });
//   }, [bpLow, bpHigh, notchFreq, bandpassEnabled, notchEnabled]);

//   useEffect(() => {
//     // init filter objects for channels
//     const f = {};
//     Object.keys(channels).forEach((ch) => {
//       f[ch] = {
//         bandpass: new Biquad("bandpass", SAMPLE_RATE, (bpLow + bpHigh) / 2, 1),
//         notch: new Biquad("notch", SAMPLE_RATE, notchFreq, 30),
//       };
//     });
//     filtersRef.current = f;
//     // eslint-disable-next-line react-hooks/exhaustive-deps
//   }, []);

//   // spectrogram canvas refs
//   const specCanvasRef = useRef(null);
//   const specBufferRef = useRef({}); // per-channel buffer for spectrogram

//   useEffect(() => {
//     // init spec buffers
//     Object.keys(channels).forEach((ch) => (specBufferRef.current[ch] = []));
//   }, []);

//   const handleMessage = (data) => {
//     // Accept two formats:
//     // 1) { type: 'EEG'|'EOG'|'EMG', channels: {Fp1: val, Fp2: val, ... }, timestamp }
//     // 2) legacy: { type: 'EEG', value: 12, channel: 'Fp1', timestamp }
//     let obj;
//     try { obj = typeof data === "string" ? JSON.parse(data) : data; } catch (e) { return; }
//     const ts = obj.timestamp || Date.now();

//     if (obj.channels) {
//       const updates = {};
//       Object.entries(obj.channels).forEach(([ch, v]) => {
//         if (!(ch in channels)) return; // ignore unknown
//         // apply filters
//         let val = v;
//         const fset = filtersRef.current[ch];
//         if (fset) {
//           if (notchEnabled) val = fset.notch.processSample(val);
//           if (bandpassEnabled) val = fset.bandpass.processSample(val);
//         }
//         updates[ch] = { time: ts, value: val };
//       });

//       setChannels((prev) => {
//         const copy = { ...prev };
//         Object.entries(updates).forEach(([ch, pt]) => {
//           const arr = copy[ch] ? copy[ch].slice() : [];
//           arr.push(pt);
//           if (arr.length > MAX_POINTS) arr.splice(0, arr.length - MAX_POINTS);
//           copy[ch] = arr;

//           // add to spectrogram buffer
//           const sb = specBufferRef.current[ch] || [];
//           sb.push(pt.value);
//           if (sb.length > 256) sb.splice(0, sb.length - 256);
//           specBufferRef.current[ch] = sb;
//         });
//         return copy;
//       });

//     } else if (obj.channel) {
//       const ch = obj.channel;
//       if (!(ch in channels)) return;
//       let val = obj.value;
//       const fset = filtersRef.current[ch];
//       if (fset) {
//         if (notchEnabled) val = fset.notch.processSample(val);
//         if (bandpassEnabled) val = fset.bandpass.processSample(val);
//       }
//       setChannels((prev) => {
//         const copy = { ...prev };
//         const arr = copy[ch] ? copy[ch].slice() : [];
//         arr.push({ time: ts, value: val });
//         if (arr.length > MAX_POINTS) arr.splice(0, arr.length - MAX_POINTS);
//         copy[ch] = arr;

//         const sb = specBufferRef.current[ch] || [];
//         sb.push(val);
//         if (sb.length > 256) sb.splice(0, sb.length - 256);
//         specBufferRef.current[ch] = sb;

//         return copy;
//       });
//     }
//   };

//   // connect / disconnect
//   const connectWS = () => {
//     if (wsRef.current) return;
//     try {
//       const ws = new WebSocket(wsUrl);
//       wsRef.current = ws;
//       ws.onopen = () => setConnected(true);
//       ws.onclose = () => { setConnected(false); wsRef.current = null; };
//       ws.onerror = () => { setConnected(false); };
//       ws.onmessage = (ev) => handleMessage(ev.data);
//     } catch (e) {
//       console.error("WebSocket error", e);
//       setConnected(false);
//     }
//   };
//   const disconnectWS = () => {
//     if (!wsRef.current) return;
//     wsRef.current.close();
//     wsRef.current = null;
//     setConnected(false);
//   };

//   // spectrogram draw loop
//   useEffect(() => {
//     let raf = null;
//     const canvas = specCanvasRef.current;
//     const ctx = canvas ? canvas.getContext("2d") : null;
//     const draw = () => {
//       if (!ctx) return;
//       const width = canvas.width;
//       const height = canvas.height;
//       ctx.fillStyle = "#0b1220";
//       ctx.fillRect(0, 0, width, height);

//       // draw spectrogram for the first selected channel (if any)
//       const ch = selectedChannels[0];
//       if (ch && specBufferRef.current[ch] && specBufferRef.current[ch].length >= 32) {
//         // compute spectrum
//         const mags = computeMagnitudeSpectrum(specBufferRef.current[ch]);
//         const binCount = mags.length || 0;
//         if (binCount > 0) {
//           // draw as vertical bars
//           const barW = Math.max(1, Math.floor(width / binCount));
//           for (let i = 0; i < binCount; i++) {
//             const m = mags[i];
//             const intensity = Math.min(1, m * 10);
//             const hue = Math.floor(240 - intensity * 240);
//             // use CSS hsl with commas for broader compatibility
//             ctx.fillStyle = `hsl(${hue}, 100%, ${10 + intensity * 80}%)`;
//             ctx.fillRect(i * barW, height - intensity * height, barW, intensity * height);
//           }
//         }
//       } else {
//         // placeholder text
//         ctx.fillStyle = "rgba(255,255,255,0.12)";
//         ctx.font = "14px Inter, Arial";
//         ctx.fillText("Spectrogram (select a channel and stream data to see FFT)", 10, height / 2);
//       }

//       raf = requestAnimationFrame(draw);
//     };
//     raf = requestAnimationFrame(draw);
//     return () => cancelAnimationFrame(raf);
//   }, [selectedChannels]);

//   // prepare recharts data for multi-line plot
//   const chartData = (() => {
//     // align by index, take last N points and build points object with channel keys
//     const chs = selectedChannels;
//     const maxLen = Math.max(...chs.map((c) => channels[c]?.length || 0), 0);
//     const out = [];
//     for (let i = Math.max(0, maxLen - 200); i < maxLen; i++) {
//       const point = {};
//       chs.forEach((c) => {
//         const arr = channels[c] || [];
//         const idx = i - (maxLen - (arr.length));
//         point[c] = idx >= 0 && arr[idx] ? arr[idx].value : null;
//       });
//       out.push(point);
//     }
//     return out;
//   })();

//   // UI helpers
//   const getGroupChannels = () => {
//     switch (selectedGroup) {
//       case "EEG": return EEG_CHANNELS;
//       case "EOG": return EOG_CHANNELS;
//       case "EMG": return EMG_CHANNELS;
//       default: return [];
//     }
//   };

//   const toggleChannel = (ch) => {
//     setSelectedChannels((prev) => {
//       if (prev.includes(ch)) return prev.filter((p) => p !== ch);
//       return [...prev.slice(0, 7), ch]; // limit to 8 channels on chart
//     });
//   };

//   return (
//     <div className="p-4 grid grid-cols-1 lg:grid-cols-4 gap-4">
//       {/* LEFT: Controls */}
//       <div className="col-span-1">
//         <Card className="rounded-2xl p-4">
//           <h3 className="text-lg font-semibold mb-2">Connection</h3>
//           <div className="flex gap-2">
//             <input value={wsUrl} onChange={(e) => setWsUrl(e.target.value)} className="flex-1 p-2 rounded-md bg-slate-800 text-white" />
//             {connected ? (
//               <Button onClick={disconnectWS}>Disconnect</Button>
//             ) : (
//               <Button onClick={connectWS}>Connect</Button>
//             )}
//           </div>
//           <p className="mt-2 text-sm text-muted-foreground">Status: {connected ? "Connected" : "Disconnected"}</p>

//           <hr className="my-4" />

//           <h3 className="text-lg font-semibold mb-2">Groups</h3>
//           <div className="flex gap-2 mb-3">
//             <Button variant={selectedGroup === "EEG" ? "default" : "ghost"} onClick={() => setSelectedGroup("EEG")}>EEG</Button>
//             <Button variant={selectedGroup === "EOG" ? "default" : "ghost"} onClick={() => setSelectedGroup("EOG")}>EOG</Button>
//             <Button variant={selectedGroup === "EMG" ? "default" : "ghost"} onClick={() => setSelectedGroup("EMG")}>EMG</Button>
//           </div>

//           <div>
//             <h4 className="font-medium">Channels (select up to 8)</h4>
//             <div className="grid grid-cols-2 gap-2 mt-2">
//               {getGroupChannels().map((ch) => (
//                 <button key={ch} onClick={() => toggleChannel(ch)} className={`p-2 rounded-md text-sm ${selectedChannels.includes(ch) ? 'bg-slate-700' : 'bg-slate-900'}`}>
//                   {ch}
//                 </button>
//               ))}
//             </div>
//           </div>

//           <hr className="my-4" />

//           <h3 className="text-lg font-semibold">Filters</h3>
//           <div className="mt-2">
//             <label className="flex items-center gap-2"><input type="checkbox" checked={notchEnabled} onChange={(e) => setNotchEnabled(e.target.checked)} /> Notch filter</label>
//             <div className="flex items-center gap-2 mt-2">
//               <input type="range" min={40} max={60} value={notchFreq} onChange={(e) => setNotchFreq(Number(e.target.value))} />
//               <span className="w-12 text-right">{notchFreq}Hz</span>
//             </div>

//             <label className="flex items-center gap-2 mt-3"><input type="checkbox" checked={bandpassEnabled} onChange={(e) => setBandpassEnabled(e.target.checked)} /> Bandpass</label>
//             <div className="flex items-center gap-2 mt-2">
//               <input type="number" value={bpLow} onChange={(e) => setBpLow(Number(e.target.value))} className="w-20 p-1 rounded-md bg-slate-900" />
//               <span>—</span>
//               <input type="number" value={bpHigh} onChange={(e) => setBpHigh(Number(e.target.value))} className="w-20 p-1 rounded-md bg-slate-900" />
//               <span className="ml-2">Hz</span>
//             </div>

//             <p className="mt-2 text-sm text-muted-foreground">Filters are applied to the visualization stream using lightweight Biquad approximations. For production you may want to validate with offline filtering or use a DSP library.</p>
//           </div>
//         </Card>

//         <Card className="rounded-2xl p-4 mt-4">
//           <h3 className="text-lg font-semibold mb-2">Spectrogram</h3>
//           <canvas ref={specCanvasRef} width={400} height={150} className="w-full rounded-md bg-black" />
//           <p className="mt-2 text-sm">Spectrogram shows magnitude spectrum for the first selected channel and updates in real-time.</p>
//         </Card>
//       </div>

//       {/* RIGHT: Charts */}
//       <div className="col-span-3 space-y-4">
//         <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }}>
//           <Card className="rounded-2xl p-4">
//             <div className="flex justify-between items-center mb-2">
//               <h2 className="text-xl font-semibold">Live Signals</h2>
//               <div className="text-sm text-muted-foreground">Showing: {selectedChannels.join(', ')}</div>
//             </div>
//             <div style={{ width: '100%', height: 280 }}>
//               <ResponsiveContainer>
//                 <LineChart data={chartData}>
//                   <XAxis dataKey={(d, idx) => idx} hide />
//                   <YAxis domain={[-200, 200]} />
//                   <Tooltip />
//                   <Legend />
//                   {selectedChannels.map((ch, i) => (
//                     <Line key={ch} type="monotone" dataKey={ch} dot={false} strokeWidth={2} stroke={`hsl(${(i * 70) % 360}, 80%, 60%)`} />
//                   ))}
//                 </LineChart>
//               </ResponsiveContainer>
//             </div>
//           </Card>
//         </motion.div>

//         <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }}>
//           <Card className="rounded-2xl p-4">
//             <h2 className="text-xl font-semibold mb-2">Per-Channel Preview</h2>
//             <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
//               {selectedChannels.map((ch) => (
//                 <Card key={ch} className="rounded-lg p-3 bg-slate-900">
//                   <CardContent>
//                     <div className="flex justify-between items-center mb-2">
//                       <strong>{ch}</strong>
//                       <span className="text-sm text-muted-foreground">samples: {channels[ch]?.length || 0}</span>
//                     </div>
//                     <div style={{ width: '100%', height: 120 }}>
//                       <ResponsiveContainer>
//                         <LineChart data={downsample((channels[ch] || []).map(pt => ({ value: pt.value })), 120)}>
//                           <XAxis dataKey="index" hide />
//                           <YAxis domain={[-200,200]} />
//                           <Line type="monotone" dataKey="value" dot={false} strokeWidth={2} />
//                         </LineChart>
//                       </ResponsiveContainer>
//                     </div>
//                   </CardContent>
//                 </Card>
//               ))}
//             </div>
//           </Card>
//         </motion.div>

//       </div>
//     </div>
//   );
// }


// import React, { useEffect, useRef, useState, useMemo } from "react";
// // NOTE: replaced framework-specific aliased UI imports with lightweight local components
// // so this component can run without needing project-specific alias configuration.

// const Card = ({ children, className = '' }) => (
//   <div className={`rounded-2xl shadow p-3 bg-white/5 ${className}`}>{children}</div>
// );
// const CardContent = ({ children }) => <div className="p-2">{children}</div>;
// const Button = ({ children, onClick, variant = 'default', className = '' }) => (
//   <button onClick={onClick} className={`px-3 py-1 rounded ${variant === 'ghost' ? 'bg-transparent' : 'bg-slate-700'} ${className}`}>{children}</button>
// );

// import { motion } from "framer-motion";
// import {
//   LineChart,
//   Line,
//   ResponsiveContainer,
//   XAxis,
//   YAxis,
//   Tooltip,
//   Legend,
//   CartesianGrid,
// } from "recharts";

// // ----- CONFIG -----
// const DEFAULT_WS = (typeof process !== "undefined" && process?.env?.NEXT_PUBLIC_BCI_WS) ? process.env.NEXT_PUBLIC_BCI_WS : "ws://localhost:8000/ws";
// const SAMPLE_RATE = 250; // Hz (assumption)
// const MAX_POINTS = 1024;
// const EEG_CHANNELS = ["Fp1", "Fp2", "F7", "F8", "C3", "C4", "P3", "P4", "O1", "O2"];
// const EOG_CHANNELS = ["Left", "Right"];
// const EMG_CHANNELS = ["Arm", "Forearm"];

// // lightweight downsample helper used by charts
// function downsampleRaw(arr, maxPoints) {
//   const a = arr || [];
//   if (a.length <= maxPoints) return a.map((d, i) => ({ index: i, value: d.value }));
//   const step = a.length / maxPoints;
//   const out = [];
//   for (let i = 0; i < maxPoints; i++) {
//     const idx = Math.floor(i * step);
//     out.push({ index: i, value: a[idx].value });
//   }
//   return out;
// }

// // -------------------
// // Existing LiveSignalPanel (unchanged) - kept for compatibility and as the primary visual panel
// // (export default remains LiveSignalPanel at bottom)
// // -------------------

// // ----- Small Biquad implementation (RBJ cookbook) -----
// class Biquad {
//   constructor(type = "bandpass", fs = SAMPLE_RATE, f0 = 50, Q = 1) {
//     this.type = type;
//     this.fs = fs;
//     this.f0 = f0;
//     this.Q = Q;
//     this.x1 = 0; // previous input
//     this.x2 = 0; // input-2
//     this.y1 = 0; // previous output
//     this.y2 = 0; // output-2
//     this.updateCoeffs();
//   }

//   updateCoeffs() {
//     const omega = (2 * Math.PI * this.f0) / this.fs;
//     const alpha = Math.sin(omega) / (2 * this.Q);
//     const cosw = Math.cos(omega);
//     let b0, b1, b2, a0, a1, a2;

//     switch (this.type) {
//       case "notch":
//         b0 = 1; b1 = -2 * cosw; b2 = 1;
//         a0 = 1 + alpha; a1 = -2 * cosw; a2 = 1 - alpha;
//         break;
//       case "bandpass":
//         b0 = alpha; b1 = 0; b2 = -alpha;
//         a0 = 1 + alpha; a1 = -2 * cosw; a2 = 1 - alpha;
//         break;
//       default:
//         b0 = 1; b1 = 0; b2 = 0; a0 = 1; a1 = 0; a2 = 0; break;
//     }

//     this.b0 = b0 / a0; this.b1 = b1 / a0; this.b2 = b2 / a0;
//     this.a1 = a1 / a0; this.a2 = a2 / a0;
//   }

//   setParams({ type, f0, Q, fs }) {
//     if (type) this.type = type;
//     if (f0) this.f0 = f0;
//     if (Q) this.Q = Q;
//     if (fs) this.fs = fs;
//     this.updateCoeffs();
//   }

//   processSample(x) {
//     const y = this.b0 * x + this.b1 * this.x1 + this.b2 * this.x2 - this.a1 * this.y1 - this.a2 * this.y2;
//     this.x2 = this.x1;
//     this.x1 = x;
//     this.y2 = this.y1;
//     this.y1 = y;
//     return y;
//   }

//   processBlock(xs) {
//     return xs.map((v) => this.processSample(v));
//   }
// }

// function fft(re, im) {
//   const n = re.length;
//   if ((n & (n - 1)) !== 0) throw new Error("FFT size must be power of two");
//   let j = 0;
//   for (let i = 1; i < n - 1; i++) {
//     let bit = n >> 1;
//     while (j & bit) {
//       j ^= bit;
//       bit >>= 1;
//     }
//     j ^= bit;
//     if (i < j) {
//       [re[i], re[j]] = [re[j], re[i]];
//       [im[i], im[j]] = [im[j], im[i]];
//     }
//   }
//   for (let len = 2; len <= n; len <<= 1) {
//     const ang = (-2 * Math.PI) / len;
//     const wlen_r = Math.cos(ang);
//     const wlen_i = Math.sin(ang);
//     for (let i = 0; i < n; i += len) {
//       let wr = 1;
//       let wi = 0;
//       for (let k = 0; k < len / 2; k++) {
//         const u_r = re[i + k];
//         const u_i = im[i + k];
//         const v_r = re[i + k + len / 2] * wr - im[i + k + len / 2] * wi;
//         const v_i = re[i + k + len / 2] * wi + im[i + k + len / 2] * wr;
//         re[i + k] = u_r + v_r;
//         im[i + k] = u_i + v_i;
//         re[i + k + len / 2] = u_r - v_r;
//         im[i + k + len / 2] = u_i - v_i;
//         const tmp_r = wr * wlen_r - wi * wlen_i;
//         wi = wr * wlen_i + wi * wlen_r;
//         wr = tmp_r;
//       }
//     }
//   }
// }

// function computeMagnitudeSpectrum(samples) {
//   if (!samples || samples.length === 0) return [];
//   let n = 1;
//   while (n < samples.length) n <<= 1;
//   const re = new Array(n).fill(0);
//   const im = new Array(n).fill(0);
//   for (let i = 0; i < samples.length; i++) re[i] = samples[i];
//   fft(re, im);
//   const mags = new Array(n / 2);
//   for (let i = 0; i < n / 2; i++) mags[i] = Math.sqrt(re[i] * re[i] + im[i] * im[i]) / n;
//   return mags;
// }

// export function AdvancedLivePanel({ wsData = null }) {
//   const [isPaused, setIsPaused] = useState(false);
//   const [timeWindowMs, setTimeWindowMs] = useState(10000);
//   const [displayMode, setDisplayMode] = useState('single');
//   const [selectedChannel, setSelectedChannel] = useState(0);
//   const [mockMode, setMockMode] = useState(false);

//   // buffers
//   const [eegByChannel, setEegByChannel] = useState({}); // {0: [{time,value}], 1: [...]} keyed by index
//   const [eogData, setEogData] = useState([]);
//   const [emgData, setEmgData] = useState([]);

//   const MAX_POINTS_PER_MESSAGE = 120;
//   const MAX_POINTS_PER_CHANNEL = 50000;

//   // pushers
//   const pushChannelPoints = (chIdx, pts) => {
//     setEegByChannel(prev => {
//       const current = prev[chIdx] ?? [];
//       const merged = [...current, ...pts];
//       const lastTs = merged.length ? merged[merged.length - 1].time : Date.now();
//       const cutoff = lastTs - timeWindowMs;
//       const trimmed = merged.filter(p => p.time >= cutoff);
//       if (trimmed.length > MAX_POINTS_PER_CHANNEL) trimmed.splice(0, trimmed.length - MAX_POINTS_PER_CHANNEL);
//       return { ...prev, [chIdx]: trimmed };
//     });
//   };

//   const pushSingleByTimeWindow = (setter, pts) => {
//     setter(prev => {
//       if (!pts || pts.length === 0) return prev;
//       const merged = [...prev, ...pts];
//       const lastTs = merged.length ? merged[merged.length - 1].time : Date.now();
//       const cutoff = lastTs - timeWindowMs;
//       let sliced = merged.filter(p => p.time >= cutoff);
//       if (sliced.length > MAX_POINTS_PER_CHANNEL) sliced = sliced.slice(-MAX_POINTS_PER_CHANNEL);
//       return sliced;
//     });
//   };

//   // helper: convert incoming payload (your frame/window style) into buffers
//   useEffect(() => {
//     if (isPaused) return;
//     if (!wsData) return;
//     let payload = null;
//     try {
//       const jsonText = typeof wsData === 'string' ? wsData : (wsData.data ?? null);
//       if (!jsonText) return;
//       payload = JSON.parse(jsonText);
//     } catch (err) {
//       console.error('AdvancedLivePanel: failed to parse wsData', err);
//       return;
//     }

//     if (!payload || !payload.window || !Array.isArray(payload.window)) return;
//     const source = (payload.source || '').toUpperCase();
//     const fs = Number(payload.fs) || 250;
//     const endTs = Number(payload.timestamp) || Date.now();
//     const channelsArr = payload.window; // array of channel arrays
//     const nChannels = channelsArr.length;
//     const samples = Array.isArray(channelsArr[0]) ? channelsArr[0] : [];
//     const n = samples.length;
//     if (n === 0) return;

//     const stride = Math.max(1, Math.floor(n / MAX_POINTS_PER_MESSAGE));
//     const timestamps = [];
//     for (let i = 0; i < n; i += stride) {
//       const offsetMs = Math.round((i - (n - 1)) * (1000 / fs));
//       timestamps.push(endTs + offsetMs);
//     }

//     if (source === 'EEG' || nChannels >= 4) {
//       for (let ch = 0; ch < nChannels; ch++) {
//         const chSamples = Array.isArray(channelsArr[ch]) ? channelsArr[ch] : [];
//         if (!chSamples || chSamples.length === 0) continue;
//         const pts = [];
//         for (let i = 0, idx = 0; i < chSamples.length; i += stride, idx++) {
//           const t = timestamps[idx] ?? (endTs - Math.round((n - 1 - i) * (1000 / fs)));
//           const v = Number(chSamples[i]);
//           pts.push({ time: t, value: Number.isFinite(v) ? v : 0 });
//         }
//         pushChannelPoints(ch, pts);
//       }
//     } else {
//       // non-EEG sources: push to EOG/EMG single-buffer
//       const samples0 = samples;
//       const pts = [];
//       for (let i = 0, idx = 0; i < samples0.length; i += stride, idx++) {
//         const t = timestamps[idx] ?? (endTs - Math.round((n - 1 - i) * (1000 / fs)));
//         const v = Number(samples0[i]);
//         pts.push({ time: t, value: Number.isFinite(v) ? v : 0 });
//       }
//       if (source === 'EOG') pushSingleByTimeWindow(setEogData, pts);
//       else if (source === 'EMG') pushSingleByTimeWindow(setEmgData, pts);
//       else {
//         if (nChannels === 2) pushSingleByTimeWindow(setEogData, pts);
//         else pushSingleByTimeWindow(setEmgData, pts);
//       }
//     }
//   }, [wsData, isPaused, timeWindowMs]); // eslint-disable-line react-hooks/exhaustive-deps

//   // Mock generator: produce frames periodically when mockMode is true
//   const mockIntervalRef = useRef(null);
//   useEffect(() => {
//     if (!mockMode) {
//       if (mockIntervalRef.current) { clearInterval(mockIntervalRef.current); mockIntervalRef.current = null; }
//       return;
//     }
//     // generate a frame every 200ms with 8 channels x 120 samples-ish
//     mockIntervalRef.current = setInterval(() => {
//       const now = Date.now();
//       const fs = 250;
//       const n = 120;
//       const window = [];
//       const nChannels = 8;
//       for (let ch = 0; ch < nChannels; ch++) {
//         const arr = new Array(n).fill(0).map((_, i) => {
//           // composite sine + noise, frequency depends on channel
//           const t = i / fs;
//           const freq = 8 + (ch % 4) * 4; // 8,12,16,20
//           return Math.sin(2 * Math.PI * freq * t) * (20 + ch) + (Math.random() * 6 - 3);
//         });
//         window.push(arr);
//       }
//       const frame = { source: 'EEG', fs: 250, timestamp: now, window };
//       // feed into the same processing pipeline by stringifying to mimic ws data
//       const ev = JSON.stringify(frame);
//       // call the same effect path by directly setting a local ref used as 'wsData'
//       // We'll push by setting a temporary state to trigger the effect – but to keep things simple,
//       // directly process using the same logic as the wsData effect code above.
//       // Reuse helper: emulate incoming wsData by calling a small internal function
//       // For simplicity, dispatch by setting wsDataRef (local) was avoided; instead we'll call a function below
//       processIncomingFrame(frame);
//     }, 200);

//     return () => { if (mockIntervalRef.current) clearInterval(mockIntervalRef.current); mockIntervalRef.current = null; }
//   }, [mockMode, timeWindowMs]);

//   // processIncomingFrame shares logic with wsData effect
//   const processIncomingFrame = (payload) => {
//     if (!payload || !payload.window || !Array.isArray(payload.window)) return;
//     const source = (payload.source || '').toUpperCase();
//     const fs = Number(payload.fs) || 250;
//     const endTs = Number(payload.timestamp) || Date.now();
//     const channelsArr = payload.window; // array of channel arrays
//     const nChannels = channelsArr.length;
//     const samples = Array.isArray(channelsArr[0]) ? channelsArr[0] : [];
//     const n = samples.length;
//     if (n === 0) return;

//     const stride = Math.max(1, Math.floor(n / MAX_POINTS_PER_MESSAGE));
//     const timestamps = [];
//     for (let i = 0; i < n; i += stride) {
//       const offsetMs = Math.round((i - (n - 1)) * (1000 / fs));
//       timestamps.push(endTs + offsetMs);
//     }

//     if (source === 'EEG' || nChannels >= 4) {
//       for (let ch = 0; ch < nChannels; ch++) {
//         const chSamples = Array.isArray(channelsArr[ch]) ? channelsArr[ch] : [];
//         if (!chSamples || chSamples.length === 0) continue;
//         const pts = [];
//         for (let i = 0, idx = 0; i < chSamples.length; i += stride, idx++) {
//           const t = timestamps[idx] ?? (endTs - Math.round((n - 1 - i) * (1000 / fs)));
//           const v = Number(chSamples[i]);
//           pts.push({ time: t, value: Number.isFinite(v) ? v : 0 });
//         }
//         pushChannelPoints(ch, pts);
//       }
//     } else {
//       const samples0 = samples;
//       const pts = [];
//       for (let i = 0, idx = 0; i < samples0.length; i += stride, idx++) {
//         const t = timestamps[idx] ?? (endTs - Math.round((n - 1 - i) * (1000 / fs)));
//         const v = Number(samples0[i]);
//         pts.push({ time: t, value: Number.isFinite(v) ? v : 0 });
//       }
//       if (source === 'EOG') pushSingleByTimeWindow(setEogData, pts);
//       else if (source === 'EMG') pushSingleByTimeWindow(setEmgData, pts);
//       else {
//         if (nChannels === 2) pushSingleByTimeWindow(setEogData, pts);
//         else pushSingleByTimeWindow(setEmgData, pts);
//       }
//     }
//   };

//   // expose a small effect to process external wsData prop when provided
//   useEffect(() => {
//     if (!wsData || isPaused || mockMode) return;
//     let payload = null;
//     try {
//       const jsonText = typeof wsData === 'string' ? wsData : (wsData.data ?? null);
//       if (!jsonText) return;
//       payload = JSON.parse(jsonText);
//     } catch (err) { console.error('AdvancedLivePanel: failed to parse wsData', err); return; }
//     processIncomingFrame(payload);
//   }, [wsData, isPaused, mockMode, timeWindowMs]);

//   // derive known channels and channels object mapping to EEG_CHANNELS names for visualization
//   const knownEegChannels = useMemo(() => Object.keys(eegByChannel).map(k => Number(k)).sort((a,b)=>a-b), [eegByChannel]);

//   // Build visualization-friendly "channels" object: { 'Fp1': [{time,value}], ... }
//   const vizChannels = useMemo(() => {
//     const out = {};
//     EEG_CHANNELS.forEach((name, idx) => {
//       out[name] = eegByChannel[idx] ? eegByChannel[idx].slice() : [];
//     });
//     return out;
//   }, [eegByChannel]);

//   // For overlay, build merged chartData across selected channels (simple index-based alignment)
//   const selectedChannelsList = useMemo(() => {
//     // pick first 4 EEG channels if overlay
//     if (displayMode === 'overlay') return EEG_CHANNELS.slice(0, 4);
//     const ch = Number(selectedChannel);
//     if (eegByChannel[ch]) return [EEG_CHANNELS[ch]];
//     const keys = Object.keys(eegByChannel);
//     if (keys.length === 0) return [EEG_CHANNELS[0]];
//     const fallback = Number(keys[0]);
//     return [EEG_CHANNELS[fallback]];
//   }, [displayMode, selectedChannel, eegByChannel]);

//   const chartData = useMemo(() => {
//     const chs = selectedChannelsList;
//     const maxLen = Math.max(...chs.map(c => (vizChannels[c] || []).length), 0);
//     const out = [];
//     for (let i = Math.max(0, maxLen - 200); i < maxLen; i++) {
//       const row = { index: i };
//       chs.forEach(c => {
//         const arr = vizChannels[c] || [];
//         const idx = i - (maxLen - arr.length);
//         row[c] = idx >= 0 && arr[idx] ? arr[idx].value : null;
//       });
//       out.push(row);
//     }
//     return out;
//   }, [vizChannels, selectedChannelsList]);

//   return (
//     <div className="space-y-4">
//       <div className="bg-white/5 rounded-lg shadow p-4">
//         <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-3">
//           <div className="flex gap-2 items-center">
//             <button onClick={() => setIsPaused(!isPaused)} className={`px-4 py-2 rounded-lg font-medium ${isPaused ? 'bg-green-600' : 'bg-yellow-600'} text-white`}>
//               {isPaused ? '▶ Resume' : '⏸ Pause'}
//             </button>

//             <label className="text-sm text-gray-300 ml-2">Time window:</label>
//             <select value={timeWindowMs} onChange={(e)=>setTimeWindowMs(Number(e.target.value))} className="px-3 py-2 border rounded-lg bg-slate-800 text-white">
//               <option value={5000}>5 s</option>
//               <option value={10000}>10 s</option>
//               <option value={30000}>30 s</option>
//               <option value={60000}>60 s</option>
//             </select>

//             <label className="ml-4 flex items-center gap-2 text-sm"><input type="checkbox" checked={mockMode} onChange={(e)=>setMockMode(e.target.checked)} /> Mock data</label>
//           </div>

//           <div className="flex gap-4 items-center">
//             <div className="flex items-center gap-2">
//               <label className="text-sm font-medium">EEG Display:</label>
//               <label className="flex items-center gap-1"><input type="radio" name="displayModeAdv" value="single" checked={displayMode==='single'} onChange={()=>setDisplayMode('single')} /><span className="text-sm ml-1">Single</span></label>
//               <label className="flex items-center gap-1"><input type="radio" name="displayModeAdv" value="overlay" checked={displayMode==='overlay'} onChange={()=>setDisplayMode('overlay')} /><span className="text-sm ml-1">Overlay</span></label>
//             </div>

//             <div>
//               <label className="text-sm text-gray-300 mr-2">Channel:</label>
//               <select value={selectedChannel} onChange={(e)=>setSelectedChannel(Number(e.target.value))} className="px-2 py-1 border rounded bg-slate-800 text-white" disabled={displayMode==='overlay'}>
//                 {knownEegChannels.length===0 && <option value={0}>0</option>}
//                 {knownEegChannels.map(ch => <option key={ch} value={ch}>Ch {ch}</option>)}
//               </select>
//             </div>
//           </div>
//         </div>
//       </div>

//       <div className="bg-slate-900 rounded-lg p-4">
//         <div className="flex justify-between items-center mb-2">
//           <h2 className="text-xl font-semibold">EEG Live</h2>
//           <div className="text-sm text-gray-300">Channels: {selectedChannelsList.join(', ')}</div>
//         </div>
//         <div style={{ width: '100%', height: 280 }}>
//           <ResponsiveContainer>
//             <LineChart data={chartData}>
//               <CartesianGrid strokeDasharray="3 3" />
//               <XAxis dataKey="index" />
//               <YAxis />
//               <Tooltip />
//               <Legend />
//               {selectedChannelsList.map((ch, i) => (
//                 <Line key={ch} type="monotone" dataKey={ch} dot={false} strokeWidth={2} stroke={`hsl(${(i*70)%360},70%,60%)`} isAnimationActive={false} connectNulls={false} />
//               ))}
//             </LineChart>
//           </ResponsiveContainer>
//         </div>
//       </div>

//       <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
//         <div className="bg-slate-900 rounded-lg p-4">
//           <h3 className="mb-2">EOG</h3>
//           <div style={{ width: '100%', height: 160 }}>
//             <ResponsiveContainer>
//               <LineChart data={downsampleRaw(eogData, 200)}>
//                 <CartesianGrid strokeDasharray="3 3" />
//                 <XAxis dataKey="index" />
//                 <YAxis />
//                 <Tooltip />
//                 <Line dataKey="value" stroke="#10b981" dot={false} isAnimationActive={false} />
//               </LineChart>
//             </ResponsiveContainer>
//           </div>
//         </div>

//         <div className="bg-slate-900 rounded-lg p-4">
//           <h3 className="mb-2">EMG</h3>
//           <div style={{ width: '100%', height: 160 }}>
//             <ResponsiveContainer>
//               <LineChart data={downsampleRaw(emgData, 200)}>
//                 <CartesianGrid strokeDasharray="3 3" />
//                 <XAxis dataKey="index" />
//                 <YAxis />
//                 <Tooltip />
//                 <Line dataKey="value" stroke="#f59e0b" dot={false} isAnimationActive={false} />
//               </LineChart>
//             </ResponsiveContainer>
//           </div>
//         </div>
//       </div>
//     </div>
//   );
// }

// export default AdvancedLivePanel;

// File: src/components/PacketDashboard.jsx
// React component to load a JSON file (expected at /data/out_of_acquisition.json),
// parse raw bytes according to user-adjustable packet format, and visualize filtered data.

import React, { useEffect, useState, useMemo } from 'react'
import '../../styles/test.css'
import data as '../../../../data/session/'

// Helper: convert hex string -> number
const hexToNum = (h) => {
  if (typeof h === 'number') return h
  return parseInt(h, 16)
}

// Default demo JSON loader will assume JSON shape: { "raw": ["C7","7C","90", ...] }
// If your file stores numbers instead of hex strings, the parser will handle that as well.

export default function PacketDashboard({ jsonUrl = '' }) {
  // Tweakers (user-adjustable)
  
  const [sync1, setSync1] = useState('C7')
  const [sync2, setSync2] = useState('7C')
  const [packetSize, setPacketSize] = useState(8)
  const [ctrIndex, setCtrIndex] = useState(2)
  const [endIndex, setEndIndex] = useState(7) // 0-based within packet
  const [ch0HIndex, setCh0HIndex] = useState(3)
  const [ch0LIndex, setCh0LIndex] = useState(4)
  const [ch1HIndex, setCh1HIndex] = useState(5)
  const [ch1LIndex, setCh1LIndex] = useState(6)
  const [rawBytes, setRawBytes] = useState([])
  const [packets, setPackets] = useState([])
  const [error, setError] = useState(null)
  const [showOnlyValid, setShowOnlyValid] = useState(true)
  const [limit, setLimit] = useState(200)

  useEffect(() => {
    // load JSON once
    fetch(jsonUrl)
      .then((r) => r.json())
      .then((j) => {
        // try to find the raw array in common keys
        const raw = j.raw ?? j.data ?? j.bytes ?? j
        // normalize to array of hex strings
        const normalized = Array.isArray(raw) ? raw.map((b) => (typeof b === 'number' ? b : ('' + b).replace(/^0x/i, '')) ) : []
        setRawBytes(normalized)
      })
      .catch((e) => setError('Failed to load JSON: ' + e.message))
  }, [jsonUrl])

  // parsing logic: find packets by looking for sync bytes then slicing packetSize
  const parsed = useMemo(() => {
    const s1 = ('' + sync1).toUpperCase()
    const s2 = ('' + sync2).toUpperCase()
    const raw = rawBytes
    const out = []
    let i = 0
    while (i <= raw.length - packetSize) {
      const b1 = ('' + raw[i]).toUpperCase()
      const b2 = ('' + raw[i + 1]).toUpperCase()
      if (b1 === s1 && b2 === s2) {
        // candidate packet
        const pkt = raw.slice(i, i + packetSize)
        // check that packet length matches
        if (pkt.length === packetSize) {
          // compute channel values (16-bit signed assumed)
          const ch0h = hexToNum(pkt[ch0HIndex])
          const ch0l = hexToNum(pkt[ch0LIndex])
          const ch1h = hexToNum(pkt[ch1HIndex])
          const ch1l = hexToNum(pkt[ch1LIndex])
          const ch0 = (ch0h << 8) | (ch0l & 0xff)
          const ch1 = (ch1h << 8) | (ch1l & 0xff)
          // convert to signed 16-bit
          const signed = (v) => (v & 0x8000) ? v - 0x10000 : v
          const ctr = hexToNum(pkt[ctrIndex])
          const endByte = pkt[endIndex]
          const validEnd = !!endByte // user might want to validate exact value; for now any byte present
          const obj = {
            offset: i,
            packet: pkt,
            ctr,
            ch0: signed(ch0),
            ch1: signed(ch1),
            endByte,
            validEnd,
          }
          out.push(obj)
        }
        i += packetSize // skip ahead - assumes non-overlapping packets
      } else {
        i += 1
      }
      if (out.length >= limit) break
    }
    return out
  }, [rawBytes, sync1, sync2, packetSize, ctrIndex, ch0HIndex, ch0LIndex, ch1HIndex, ch1LIndex, endIndex, limit])

  useEffect(() => setPackets(parsed), [parsed])

  // simple svg sparkline generator for a channel
  const Sparkline = ({ values, height = 40, width = 300 }) => {
    if (!values || values.length === 0) return <div className="sparkline empty">No data</div>
    const min = Math.min(...values)
    const max = Math.max(...values)
    const range = max - min || 1
    const step = width / (values.length - 1 || 1)
    const points = values.map((v, i) => `${(i * step).toFixed(2)},${((1 - (v - min) / range) * height).toFixed(2)}`).join(' ')
    return (
      <svg className="sparkline" viewBox={`0 0 ${width} ${height}`} preserveAspectRatio="none">
        <polyline points={points} fill="none" strokeWidth={1.5} />
      </svg>
    )
  }

  // quick auto-detect: attempt to find most common sync pair and packet size
  const autoDetect = () => {
    const candidatePairs = {}
    for (let i = 0; i < rawBytes.length - 1; i++) {
      const a = ('' + rawBytes[i]).toUpperCase()
      const b = ('' + rawBytes[i + 1]).toUpperCase()
      const key = a + ' ' + b
      candidatePairs[key] = (candidatePairs[key] || 0) + 1
    }
    const pairs = Object.entries(candidatePairs).sort((a, b) => b[1] - a[1])
    if (pairs.length > 0) {
      const [best] = pairs[0]
      const [a, b] = best.split(' ')
      setSync1(a)
      setSync2(b)
    }
    // heuristic for packet size: look for repeated distance between repeated syncs
    const syncOffsets = []
    for (let i = 0; i < rawBytes.length - 1; i++) {
      if ((('' + rawBytes[i]).toUpperCase()) === ('' + sync1).toUpperCase() && (('' + rawBytes[i+1]).toUpperCase()) === (''+sync2).toUpperCase()) {
        syncOffsets.push(i)
      }
    }
    if (syncOffsets.length >= 2) {
      const diffs = []
      for (let i = 1; i < syncOffsets.length; i++) diffs.push(syncOffsets[i] - syncOffsets[i-1])
      const mode = diffs.sort((a,b)=>diffs.filter(x=>x===a).length - diffs.filter(x=>x===b).length).pop()
      if (mode) setPacketSize(mode)
    }
  }

  return (
    <div className="dashboard-root">
      <header className="dash-header">
        <h1>Arduino Packet Filter Dashboard</h1>
        <div className="summary">
          <div>Raw bytes: {rawBytes.length}</div>
          <div>Parsed packets: {packets.length}</div>
          <div>Packet size (current): {packetSize}</div>
        </div>
      </header>

      <section className="controls">
        <div className="control-grid">
          <div className="control">
            <label>Sync Byte 1 (hex)</label>
            <input value={sync1} onChange={(e)=>setSync1(e.target.value.trim())} />
          </div>
          <div className="control">
            <label>Sync Byte 2 (hex)</label>
            <input value={sync2} onChange={(e)=>setSync2(e.target.value.trim())} />
          </div>
          <div className="control">
            <label>Packet Size</label>
            <input type="number" min={4} value={packetSize} onChange={(e)=>setPacketSize(Number(e.target.value)||1)} />
          </div>
          <div className="control">
            <label>CTR index</label>
            <input type="number" value={ctrIndex} onChange={(e)=>setCtrIndex(Number(e.target.value))} />
          </div>
          <div className="control">
            <label>End index</label>
            <input type="number" value={endIndex} onChange={(e)=>setEndIndex(Number(e.target.value))} />
          </div>

          <div className="control small"> 
            <label>Ch0 H</label>
            <input type="number" value={ch0HIndex} onChange={(e)=>setCh0HIndex(Number(e.target.value))} />
          </div>
          <div className="control small"> 
            <label>Ch0 L</label>
            <input type="number" value={ch0LIndex} onChange={(e)=>setCh0LIndex(Number(e.target.value))} />
          </div>
          <div className="control small"> 
            <label>Ch1 H</label>
            <input type="number" value={ch1HIndex} onChange={(e)=>setCh1HIndex(Number(e.target.value))} />
          </div>
          <div className="control small"> 
            <label>Ch1 L</label>
            <input type="number" value={ch1LIndex} onChange={(e)=>setCh1LIndex(Number(e.target.value))} />
          </div>

          <div className="control actions">
            <button onClick={()=>setPackets(parsed)}>Apply</button>
            <button onClick={autoDetect}>Auto-detect</button>
            <button onClick={()=>{ setSync1('C7'); setSync2('7C'); setPacketSize(8); setCtrIndex(2); setEndIndex(7); setCh0HIndex(3); setCh0LIndex(4); setCh1HIndex(5); setCh1LIndex(6) }}>Reset</button>
          </div>

        </div>

        <div className="toggles">
          <label><input type="checkbox" checked={showOnlyValid} onChange={(e)=>setShowOnlyValid(e.target.checked)} /> Show only valid</label>
          <label style={{marginLeft: '1rem'}}>Limit packets: <input type="number" value={limit} onChange={(e)=>setLimit(Number(e.target.value))} style={{width:80}}/></label>
        </div>

      </section>

      <section className="visuals">
        <div className="panel">
          <h2>Channels Overview</h2>
          <div className="sparks">
            <div className="spark-wrap">
              <h3>Channel 0</h3>
              <Sparkline values={packets.filter((p,i)=>!showOnlyValid||p.validEnd).map(p=>p.ch0)} />
            </div>
            <div className="spark-wrap">
              <h3>Channel 1</h3>
              <Sparkline values={packets.filter((p,i)=>!showOnlyValid||p.validEnd).map(p=>p.ch1)} />
            </div>
          </div>
        </div>

        <div className="panel">
          <h2>Parsed Packets</h2>
          <div className="table-wrap">
            <table className="packets-table">
              <thead>
                <tr>
                  <th>#</th>
                  <th>Offset</th>
                  <th>CTR</th>
                  <th>Ch0</th>
                  <th>Ch1</th>
                  <th>End</th>
                  <th>Bytes</th>
                </tr>
              </thead>
              <tbody>
                {packets.filter((p)=>!showOnlyValid || p.validEnd).map((p, idx) => (
                  <tr key={idx} className={p.validEnd ? 'valid' : 'invalid'}>
                    <td>{idx}</td>
                    <td>{p.offset}</td>
                    <td>{p.ctr}</td>
                    <td>{p.ch0}</td>
                    <td>{p.ch1}</td>
                    <td>{('' + p.endByte).toUpperCase()}</td>
                    <td className="bytes">{p.packet.map(b=>(''+b).toUpperCase()).join(' ')}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </section>

      {error && <div className="error">{error}</div>}

      <footer className="dash-footer">Tip: Place your out_of_acquisition JSON at <code>/data/out_of_acquisition.json</code>. See the top of the file for expected JSON shapes.</footer>
    </div>
  )
}
