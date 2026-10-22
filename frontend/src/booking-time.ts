// Convert a wall-clock choice to an explicit instant without using the PC's timezone.
// Refuse nonexistent and repeated daylight-saving times instead of guessing.
export function bookingInterval(local:string,zone:string,duration:number){
 const match=/^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})$/.exec(local)
 if(!match)throw new Error('Choisissez la date et l’heure du rendez-vous.')
 if(!Number.isInteger(duration)||duration<15||duration>240)throw new Error('Choisissez une durée entre 15 minutes et 4 heures.')
 const wall=Date.UTC(+match[1]!,+match[2]!-1,+match[3]!,+match[4]!,+match[5]!)
 const formatter=new Intl.DateTimeFormat('en-CA',{timeZone:zone,year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',second:'2-digit',hourCycle:'h23'})
 function parts(instant:number){return Object.fromEntries(formatter.formatToParts(new Date(instant)).map(part=>[part.type,part.value]))}
 function offset(instant:number){const p=parts(instant);return Date.UTC(+p.year!,+p.month!-1,+p.day!,+p.hour!,+p.minute!,+p.second!)-instant}
 const offsets=new Set([-36,0,36].map(hours=>offset(wall+hours*3600000)))
 const candidates=[...offsets].map(value=>wall-value).filter(instant=>{const p=parts(instant);return `${p.year}-${p.month}-${p.day}T${p.hour}:${p.minute}`===local})
 if(candidates.length!==1)throw new Error('Cet horaire est inexistant ou ambigu lors du changement d’heure. Choisissez un autre créneau.')
 function explicit(instant:number){const p=parts(instant),minutes=offset(instant)/60000,absolute=Math.abs(minutes);return `${p.year}-${p.month}-${p.day}T${p.hour}:${p.minute}:00${minutes>=0?'+':'-'}${String(Math.floor(absolute/60)).padStart(2,'0')}:${String(absolute%60).padStart(2,'0')}`}
 const start=candidates[0]!
 return {starts_at:explicit(start),ends_at:explicit(start+duration*60000),timezone:zone}
}
