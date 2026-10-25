/* Keep in sync with planning/palette.py. Calendar dates use UTC to avoid timezone shifts. */
(()=>{const colors={Arbeitstag:'#e5e5e5',Urlaub:'#ff6b6b',Ruhetag:'#c6efce',Ungeplant:'#eef0f3',Feiertag:'#ff80c0',Wochenende:'#fff176'};
function weekend(day){return [0,6].includes(new Date(day.date+'T00:00:00Z').getUTCDay());}
function base(day){return colors[['Urlaub','Ruhetag'].includes(day.kind)?day.kind:weekend(day)?'Wochenende':day.kind]||colors.Ungeplant;}
function apply(node,day){const color=base(day);node.dataset.weekend=String(weekend(day));node.style.backgroundColor=day.is_holiday?colors.Feiertag:color;node.style.backgroundImage=day.is_holiday&&day.kind!=='Ungeplant'?`linear-gradient(135deg,${colors.Feiertag} 0 50%,${color} 50% 100%)`:'none';}
window.PlanColors={colors,weekend,base,apply};})();
