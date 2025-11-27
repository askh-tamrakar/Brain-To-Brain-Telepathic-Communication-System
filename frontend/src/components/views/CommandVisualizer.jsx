// import React, { useState, useEffect } from 'react'
// import '../../styles/CommandVisualizer.css'

// export default function CommandVisualizer({ wsData }) {
//   const [commands, setCommands] = useState([])
//   const [liveText, setLiveText] = useState('')
//   const [activeKey, setActiveKey] = useState(null)
  
//   const keyboard = [
//     ['1', '2', '3', '4', '5', '7', '8', '9', '0']
//     ['Q', 'W', 'E', 'R', 'T', 'Y', 'U', 'I', 'O', 'P'],
//     ['A', 'S', 'D', 'F', 'G', 'H', 'J', 'K', 'L'],
//     ['Z', 'X', 'C', 'V', 'B', 'N', 'M'],
//     ['SPACE' ]
//   ]
  
//   useEffect(() => {
//     if (!wsData) return
    
//     try {
//       const parsed = JSON.parse(wsData.data)
//       if (parsed.type !== 'command') return
      
//       const cmd = { ...parsed, id: Date.now() }
//       setCommands(prev => [cmd, ...prev].slice(0, 20))
      
//       setActiveKey(parsed.command)
//       setTimeout(() => setActiveKey(null), 300)
      
//       if (parsed.command === 'ENTER') {
//         // Trigger enter animation
//       } else if (parsed.command === 'BACKSPACE') {
//         setLiveText(prev => prev.slice(0, -1))
//       } else {
//         setLiveText(prev => prev + parsed.command)
//       }
//     } catch (e) {
//       console.error('Command parse error:', e)
//     }
//   }, [wsData])
  
//   return (
//     <div className="space-y-4">
//       <div className="bg-white rounded-lg shadow p-6">
//         <h2 className="text-2xl font-bold text-gray-800 mb-4">Command Recognition</h2>
        
//         <div className="bg-gray-100 rounded-lg p-4 mb-4">
//           <div className="text-sm text-gray-600 mb-2">Live Text Preview:</div>
//           <div className="text-2xl font-mono min-h-[3rem] bg-white rounded p-3">
//             {liveText || <span className="text-gray-400">Waiting for input...</span>}
//           </div>
//         </div>
        
//         <div className="space-y-2 mb-4">
//           {keyboard.map((row, i) => (
//             <div key={i} className="flex justify-center gap-2">
//               {row.map(key => (
//                 <div
//                   key={key}
//                   className={`command-key w-12 h-12 flex items-center justify-center rounded-lg border-2 font-semibold transition-all
//                     ${activeKey === key 
//                       ? 'bg-blue-600 border-blue-500 text-white scale-110' 
//                       : 'border-gray-300 bg-white text-gray-700'}`}
//                 >
//                   {key}
//                 </div>
//               ))}
//             </div>
//           ))}
//           <div className="flex justify-center gap-2 mt-4">
//             <div 
//               className={`command-key px-6 h-12 flex items-center justify-center rounded-lg border-2 font-semibold transition-all
//                 ${activeKey === 'BACKSPACE' 
//                   ? 'bg-blue-600 border-blue-500 text-white scale-110' 
//                   : 'border-gray-300 bg-white text-gray-700'}`}
//             >
//               ⌫ BACK
//             </div>
//             <div 
//               className={`command-key px-12 h-12 flex items-center justify-center rounded-lg border-2 font-semibold transition-all
//                 ${activeKey === 'ENTER' 
//                   ? 'bg-green-600 border-green-500 text-white scale-110' 
//                   : 'border-gray-300 bg-white text-gray-700'}`}
//             >
//               ↵ ENTER
//             </div>
//           </div>
//         </div>
//       </div>
      
//       <div className="bg-white rounded-lg shadow p-6">
//         <h3 className="text-lg font-semibold text-gray-800 mb-4">Command Timeline</h3>
//         <div className="space-y-2 max-h-64 overflow-y-auto scrollbar-hide">
//           {commands.length === 0 ? (
//             <p className="text-gray-500 text-center py-8">Waiting for recognized commands...</p>
//           ) : (
//             commands.map(cmd => (
//               <div key={cmd.id} className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
//                 <div className="flex items-center gap-3">
//                   <span className="text-2xl font-bold text-blue-600">{cmd.command}</span>
//                   <span className="text-sm text-gray-600">
//                     {new Date(cmd.timestamp).toLocaleTimeString()}
//                   </span>
//                 </div>
//                 <div className="text-sm font-medium text-gray-700">
//                   {(cmd.confidence * 100).toFixed(1)}%
//                 </div>
//               </div>
//             ))
//           )}
//         </div>
//       </div>
//     </div>
//   )
// }

import React, { useState, useEffect } from "react";
import "../../styles/CommandVisualizer.css";

export default function CommandVisualizer({ wsData }) {
  const [commands, setCommands] = useState([]);
  const [liveText, setLiveText] = useState("");
  const [activeKey, setActiveKey] = useState(null);

  // Converted from your HTML keyboard layout
  const keyboard = [
    ["F1", "F2", "F3", "F4", "F5", "F6", "F7", "F8", "F9", "F10", "F11", "F12"],
    ["Tab", "Q", "W", "E", "R", "T", "Y", "U", "I", "O", "P", "Backspace"],
    ["Caps", "A", "S", "D", "F", "G", "H", "J", "K", "L", "Enter"],
    ["Shift", "Z", "X", "C", "V", "B", "N", "M", "Shift"],
    ["Ctrl", "Alt", "SPACE", "Alt", "Ctrl"],
  ];

  useEffect(() => {
    if (!wsData) return;

    try {
      const parsed = JSON.parse(wsData.data);
      if (parsed.type !== "command") return;

      const cmd = { ...parsed, id: Date.now() };
      setCommands((prev) => [cmd, ...prev].slice(0, 20));

      setActiveKey(parsed.command);
      setTimeout(() => setActiveKey(null), 300);

      // Live text logic
      if (parsed.command === "ENTER") {
        // Enter action (optional)
      } else if (parsed.command === "BACKSPACE") {
        setLiveText((prev) => prev.slice(0, -1));
      } else {
        setLiveText((prev) => prev + parsed.command);
      }
    } catch (e) {
      console.error("Command parse error:", e);
    }
  }, [wsData]);

  return (
    <div className="space-y-4">

      {/* -------------------- MAIN PANEL -------------------- */}
      <div className="bg-white rounded-lg shadow p-6">
        <h2 className="text-2xl font-bold text-gray-800 mb-4">
          Command Recognition
        </h2>

        {/* Live Text */}
        <div className="bg-gray-100 rounded-lg p-4 mb-4">
          <div className="text-sm text-gray-600 mb-2">Live Text Preview:</div>
          <div className="text-2xl font-mono min-h-[3rem] bg-white rounded p-3">
            {liveText || <span className="text-gray-400">Waiting for input...</span>}
          </div>
        </div>

        {/* -------------------- KEYBOARD -------------------- */}
        <div className="space-y-2 mb-4">
          {keyboard.map((row, i) => (
            <div key={i} className="flex justify-center gap-2">
              {row.map((key) => {
                const IS_SPACE = key === "SPACE";
                const IS_WIDE =
                  ["Tab", "Backspace", "Caps", "Enter", "Shift"].includes(key);
                const IS_EXTRA_WIDE = key === "SPACE";

                const sizeClasses = IS_EXTRA_WIDE
                  ? "px-24"
                  : IS_WIDE
                  ? "px-10"
                  : "w-12";

                return (
                  <div
                    key={key}
                    className={`command-key ${sizeClasses} h-12 flex items-center justify-center rounded-lg border-2 font-semibold transition-all
                      ${
                        activeKey === key
                          ? "bg-blue-600 border-blue-500 text-white scale-110"
                          : "border-gray-300 bg-white text-gray-700"
                      }`}
                  >
                    {IS_SPACE ? "Space" : key}
                  </div>
                );
              })}
            </div>
          ))}

          {/* BACKSPACE + ENTER */}
          <div className="flex justify-center gap-2 mt-4">
            <div
              className={`command-key px-6 h-12 flex items-center justify-center rounded-lg border-2 font-semibold transition-all
                ${
                  activeKey === "BACKSPACE"
                    ? "bg-blue-600 border-blue-500 text-white scale-110"
                    : "border-gray-300 bg-white text-gray-700"
                }`}
            >
              ⌫ BACK
            </div>

            <div
              className={`command-key px-12 h-12 flex items-center justify-center rounded-lg border-2 font-semibold transition-all
                ${
                  activeKey === "ENTER"
                    ? "bg-green-600 border-green-500 text-white scale-110"
                    : "border-gray-300 bg-white text-gray-700"
                }`}
            >
              ↵ ENTER
            </div>
          </div>
        </div>
      </div>

      {/* -------------------- COMMAND FEED -------------------- */}
      <div className="bg-white rounded-lg shadow p-6">
        <h3 className="text-lg font-semibold text-gray-800 mb-4">
          Command Timeline
        </h3>

        <div className="space-y-2 max-h-64 overflow-y-auto scrollbar-hide">
          {commands.length === 0 ? (
            <p className="text-gray-500 text-center py-8">
              Waiting for recognized commands...
            </p>
          ) : (
            commands.map((cmd) => (
              <div
                key={cmd.id}
                className="flex items-center justify-between p-3 bg-gray-50 rounded-lg"
              >
                <div className="flex items-center gap-3">
                  <span className="text-2xl font-bold text-blue-600">
                    {cmd.command}
                  </span>
                  <span className="text-sm text-gray-600">
                    {new Date(cmd.timestamp).toLocaleTimeString()}
                  </span>
                </div>
                <div className="text-sm font-medium text-gray-700">
                  {(cmd.confidence * 100).toFixed(1)}%
                </div>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}
