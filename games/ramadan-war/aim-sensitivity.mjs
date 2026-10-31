// Pure, bounded and backward-compatible sensitivity settings for pointer aiming.
export const AIM_LEVELS = Object.freeze(['low','normal','high']);
export function readAimSensitivity(value) { return AIM_LEVELS.includes(value) ? value : 'normal'; }
export function aimMultiplier(value) { return ({low:0.65,normal:1,high:1.4})[readAimSensitivity(value)]; }
export function nextAimSensitivity(value) { const i=AIM_LEVELS.indexOf(readAimSensitivity(value));return AIM_LEVELS[(i+1)%AIM_LEVELS.length]; }
export function aimSensitivityLabel(value) {return ({low:'کم',normal:'معمولی',high:'زیاد'})[readAimSensitivity(value)];}
