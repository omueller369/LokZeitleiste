/* Keep in sync with planning/palette.py. Calendar dates use UTC to avoid timezone shifts. */
(()=>{const colors={Arbeitstag:'#f5f5f5',Urlaub:'#ff7256',Ruhetag:'#66cdaa',Ungeplant:'#eef0f3',Feiertag:'#ffe4e1',Wochenende:'#eedc82'};
function weekend(day){return [0,6].includes(new Date(day.date+'T00:00:00Z').getUTCDay());}
function base(day){return colors[['Urlaub','Ruhetag'].includes(day.kind)?day.kind:weekend(day)?'Wochenende':day.kind]||colors.Ungeplant;}
function apply(node,day){const color=base(day);node.dataset.weekend=String(weekend(day));node.style.backgroundColor=day.is_holiday?colors.Feiertag:color;node.style.backgroundImage=day.is_holiday&&day.kind!=='Ungeplant'?`linear-gradient(135deg,${colors.Feiertag} 0 50%,${color} 50% 100%)`:'none';}
function yearSlots(month){const offset=month.days.length?(new Date(month.days[0].date+'T00:00:00Z').getUTCDay()+6)%7:0;return Array.from({length:37},(_,i)=>month.days[i-offset]||null);}
function weekdayInitial(date){return new Intl.DateTimeFormat(window.I18n?.locale||'de-DE',{weekday:'long',timeZone:'UTC'}).format(new Date(date+'T00:00:00Z')).slice(0,1);}
window.PlanColors={colors,weekend,base,apply,yearSlots,weekdayInitial};})();
