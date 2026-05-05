"""
CPU Scheduling Simulator
------------------------
Works on both desktop (VS Code) and Pydroid 3 (Android).

Run:
    python OS.py
Then open: http://127.0.0.1:5000  (auto-opens in default browser)

Algorithms: FCFS, SJF (non-preemptive), Round Robin, Priority, Adaptive.
"""

import sys
import threading
import webbrowser

try:
    from flask import Flask, request, jsonify, render_template_string
except ImportError:
    print("ERROR: Flask is not installed.\n"
          "  - VS Code / Desktop : pip install flask\n"
          "  - Pydroid 3         : Menu -> Pip -> install 'flask'")
    sys.exit(1)

app = Flask(__name__)


# ---------------- Scheduling Algorithms ----------------

def _finalize(p, ct, first_run):
    tat = ct - p['arrival']
    wt = tat - p['burst']
    rt = first_run - p['arrival']
    return {
        'pid': p['pid'], 'arrival': p['arrival'], 'burst': p['burst'],
        'priority': p.get('priority'),
        'ct': ct, 'tat': tat, 'wt': wt, 'rt': rt
    }


def _add_idle(gantt, start, end):
    if end > start:
        gantt.append({'pid': 'IDLE', 'start': start, 'end': end})


def fcfs(processes):
    procs = sorted([p.copy() for p in processes],
                   key=lambda p: (p['arrival'], p['pid']))
    time = 0
    gantt = []
    results = []
    for p in procs:
        if time < p['arrival']:
            _add_idle(gantt, time, p['arrival'])
            time = p['arrival']
        start = time
        time += p['burst']
        gantt.append({'pid': p['pid'], 'start': start, 'end': time})
        results.append(_finalize(p, time, start))
    return results, gantt


def sjf(processes):
    procs = [p.copy() for p in processes]
    n = len(procs)
    time = 0
    gantt = []
    results = []
    done = set()
    while len(done) < n:
        available = [p for p in procs
                     if p['arrival'] <= time and p['pid'] not in done]
        if not available:
            next_arrival = min(p['arrival'] for p in procs
                               if p['pid'] not in done)
            _add_idle(gantt, time, next_arrival)
            time = next_arrival
            continue
        chosen = min(available, key=lambda p: (p['burst'], p['arrival'], p['pid']))
        done.add(chosen['pid'])
        start = time
        time += chosen['burst']
        gantt.append({'pid': chosen['pid'], 'start': start, 'end': time})
        results.append(_finalize(chosen, time, start))
    results.sort(key=lambda r: (r['arrival'], r['pid']))
    return results, gantt


def priority_scheduling(processes):
    for p in processes:
        if p.get('priority') is None:
            raise ValueError(
                f"Process {p['pid']} is missing a priority value. "
                f"Priority Scheduling requires a priority number for every process."
            )
    procs = [p.copy() for p in processes]
    n = len(procs)
    time = 0
    gantt = []
    results = []
    done = set()
    while len(done) < n:
        available = [p for p in procs
                     if p['arrival'] <= time and p['pid'] not in done]
        if not available:
            next_arrival = min(p['arrival'] for p in procs
                               if p['pid'] not in done)
            _add_idle(gantt, time, next_arrival)
            time = next_arrival
            continue
        chosen = min(available,
                     key=lambda p: (p['priority'], p['arrival'], p['pid']))
        done.add(chosen['pid'])
        start = time
        time += chosen['burst']
        gantt.append({'pid': chosen['pid'], 'start': start, 'end': time})
        results.append(_finalize(chosen, time, start))
    results.sort(key=lambda r: (r['arrival'], r['pid']))
    return results, gantt


def round_robin(processes, quantum):
    if quantum is None or quantum <= 0:
        raise ValueError("Time quantum must be a positive integer (>= 1).")

    procs = sorted([p.copy() for p in processes],
                   key=lambda p: (p['arrival'], p['pid']))
    for p in procs:
        p['remaining'] = p['burst']
        p['first_run'] = -1

    n = len(procs)
    time = 0
    gantt = []
    results = []
    queue = []
    i = 0
    finished = 0

    while i < n and procs[i]['arrival'] <= time:
        queue.append(procs[i])
        i += 1

    while finished < n:
        if not queue:
            next_arrival = procs[i]['arrival']
            _add_idle(gantt, time, next_arrival)
            time = next_arrival
            while i < n and procs[i]['arrival'] <= time:
                queue.append(procs[i])
                i += 1
            continue

        p = queue.pop(0)
        if p['first_run'] == -1:
            p['first_run'] = time

        run = min(quantum, p['remaining'])
        start = time
        time += run
        p['remaining'] -= run

        if gantt and gantt[-1]['pid'] == p['pid'] and gantt[-1]['end'] == start:
            gantt[-1]['end'] = time
        else:
            gantt.append({'pid': p['pid'], 'start': start, 'end': time})

        while i < n and procs[i]['arrival'] <= time:
            queue.append(procs[i])
            i += 1

        if p['remaining'] > 0:
            queue.append(p)
        else:
            results.append(_finalize(p, time, p['first_run']))
            finished += 1

    results.sort(key=lambda r: (r['arrival'], r['pid']))
    return results, gantt


def compute_averages(results):
    n = len(results)
    if n == 0:
        return {'avg_wt': 0, 'avg_tat': 0, 'avg_rt': 0}
    return {
        'avg_wt':  round(sum(r['wt']  for r in results) / n, 2),
        'avg_tat': round(sum(r['tat'] for r in results) / n, 2),
        'avg_rt':  round(sum(r['rt']  for r in results) / n, 2),
    }


def adaptive_scheduler(processes, quantum):
    bursts = [p['burst'] for p in processes]
    avg_burst = sum(bursts) / len(bursts)
    all_have_priority = all(p.get('priority') is not None for p in processes)

    if all_have_priority:
        algo = 'Priority Scheduling'
        reason = ('All processes have a priority value. '
                  'Priority Scheduling is selected to respect process urgency.')
        results, gantt = priority_scheduling(processes)
    elif avg_burst <= 10:
        algo = 'SJF (Non-Preemptive)'
        reason = (f'Average burst time is {round(avg_burst, 2)} (<= 10). '
                  'Short bursts favour SJF which minimises waiting time.')
        results, gantt = sjf(processes)
    else:
        algo = 'Round Robin'
        reason = (f'Average burst time is {round(avg_burst, 2)} (> 10). '
                  f'Longer bursts favour Round Robin (Q={quantum}) for fair CPU sharing.')
        results, gantt = round_robin(processes, quantum)

    return results, gantt, algo, reason


# ---------------- Routes ----------------

@app.route('/')
def index():
    return render_template_string(HTML_PAGE)


def _validate(processes):
    if not processes:
        return 'Please add at least one process.'
    seen = set()
    for p in processes:
        pid = p.get('pid')
        if pid in seen:
            return f'Duplicate PID detected: {pid}'
        seen.add(pid)
        if not isinstance(p.get('burst'), int) or p['burst'] <= 0:
            return f"Process {pid}: Burst time must be an integer > 0."
        if not isinstance(p.get('arrival'), int) or p['arrival'] < 0:
            return f"Process {pid}: Arrival time must be an integer >= 0."
        if p.get('priority') is not None and (
                not isinstance(p['priority'], int) or p['priority'] < 0):
            return f"Process {pid}: Priority must be an integer >= 0."
    return None


@app.route('/simulate', methods=['POST'])
def simulate():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({'error': 'No JSON data received.'}), 400

    processes = data.get('processes', [])
    algorithm = data.get('algorithm', 'fcfs')
    try:
        quantum = int(data.get('quantum', 2))
    except (TypeError, ValueError):
        return jsonify({'error': 'Quantum must be an integer.'}), 400

    err = _validate(processes)
    if err:
        return jsonify({'error': err}), 400

    try:
        if algorithm == 'fcfs':
            results, gantt = fcfs(processes)
            selected_algo, reason = 'FCFS', ''
        elif algorithm == 'sjf':
            results, gantt = sjf(processes)
            selected_algo, reason = 'SJF (Non-Preemptive)', ''
        elif algorithm == 'rr':
            results, gantt = round_robin(processes, quantum)
            selected_algo, reason = f'Round Robin (Quantum = {quantum})', ''
        elif algorithm == 'priority':
            results, gantt = priority_scheduling(processes)
            selected_algo, reason = 'Priority Scheduling', ''
        elif algorithm == 'adaptive':
            results, gantt, selected_algo, reason = adaptive_scheduler(processes, quantum)
        else:
            return jsonify({'error': 'Unknown algorithm selected.'}), 400
    except ValueError as e:
        return jsonify({'error': str(e)}), 400

    return jsonify({
        'algorithm': selected_algo,
        'reason':    reason,
        'results':   results,
        'gantt':     gantt,
        'averages':  compute_averages(results)
    })


@app.route('/compare', methods=['POST'])
def compare():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({'error': 'No JSON data received.'}), 400

    processes = data.get('processes', [])
    try:
        quantum = int(data.get('quantum', 2))
    except (TypeError, ValueError):
        quantum = 2

    err = _validate(processes)
    if err:
        return jsonify({'error': err}), 400

    algos = [
        ('FCFS',                       lambda: fcfs(processes)),
        ('SJF (Non-Preemptive)',       lambda: sjf(processes)),
        (f'Round Robin (Q={quantum})', lambda: round_robin(processes, quantum)),
        ('Priority Scheduling',        lambda: priority_scheduling(processes)),
    ]

    comparison = []
    for name, fn in algos:
        try:
            results, gantt = fn()
            comparison.append({
                'algorithm': name, 'results': results,
                'gantt': gantt, 'averages': compute_averages(results)
            })
        except Exception as e:
            comparison.append({'algorithm': name, 'error': str(e)})

    valid = [c for c in comparison if 'averages' in c]
    best  = min(valid, key=lambda c: c['averages']['avg_wt']) if valid else None

    return jsonify({
        'comparison':     comparison,
        'best_algorithm': best['algorithm']            if best else 'N/A',
        'best_avg_wt':    best['averages']['avg_wt']   if best else 0,
        'best_avg_tat':   best['averages']['avg_tat']  if best else 0
    })


# ---------------- Frontend ----------------

HTML_PAGE = r"""
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1.0"/>
<title>CPU Scheduling Simulator</title>

<!-- Non-blocking Google Fonts (works offline too thanks to fallbacks) -->
<link rel="preconnect" href="https://fonts.googleapis.com" crossorigin>
<link rel="stylesheet"
      href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600;700&family=Sora:wght@300;400;600;700&display=swap"
      media="print" onload="this.media='all'">

<style>
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}

:root{
  --bg:#080c18;
  --s1:#0d1120;
  --s2:#111829;
  --s3:#161e33;
  --border:#1c2540;
  --border2:#243060;
  --accent:#4f8eff;
  --green:#00dfa2;
  --red:#ff5e7a;
  --yellow:#ffd166;
  --purple:#c084fc;
  --idle:#3a4566;
  --text:#dde4f5;
  --dim:#6b7899;
  --r:10px;
  --mono:'JetBrains Mono', ui-monospace, 'Courier New', monospace;
  --sans:'Sora', system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif;
}

html,body{overflow-x:hidden;}
body{
  background:var(--bg);
  color:var(--text);
  font-family:var(--sans);
  min-height:100vh;
  -webkit-tap-highlight-color:transparent;
}

body::before{
  content:'';
  position:fixed;inset:0;pointer-events:none;z-index:0;
  background:
    radial-gradient(ellipse 70% 40% at 15% 0%,rgba(79,142,255,.08) 0%,transparent 65%),
    radial-gradient(ellipse 50% 40% at 85% 100%,rgba(0,223,162,.05) 0%,transparent 60%);
}

header{
  text-align:center;
  padding:44px 16px 28px;
  position:relative;z-index:1;
  border-bottom:1px solid var(--border);
  background:linear-gradient(180deg,rgba(79,142,255,.03) 0%,transparent 100%);
}

.badge{
  display:inline-flex;align-items:center;gap:6px;
  background:var(--s2);border:1px solid var(--border2);
  border-radius:100px;padding:5px 14px;
  font-family:var(--mono);font-size:10px;color:var(--green);
  letter-spacing:2px;text-transform:uppercase;margin-bottom:14px;
}
.badge-dot{width:6px;height:6px;border-radius:50%;background:var(--green);animation:pulse 2s infinite;}
@keyframes pulse{0%,100%{opacity:1;transform:scale(1)}50%{opacity:.4;transform:scale(.8)}}

h1{
  font-size:clamp(22px,5.5vw,46px);font-weight:700;letter-spacing:-1px;
  background:linear-gradient(130deg,#fff 0%,var(--accent) 55%,var(--green) 100%);
  -webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;
  line-height:1.15;margin-bottom:8px;
}
header p{color:var(--dim);font-size:13px;font-weight:300;}

.wrap{
  max-width:1100px;margin:0 auto;
  padding:24px 16px 80px;
  position:relative;z-index:1;
}

.card{
  background:var(--s1);
  border:1px solid var(--border);
  border-radius:var(--r);
  padding:20px;
  margin-bottom:20px;
}
.card-head{
  display:flex;align-items:center;gap:8px;
  font-family:var(--mono);font-size:10px;color:var(--dim);
  text-transform:uppercase;letter-spacing:2px;margin-bottom:18px;
}

.col-labels,
.process-row{
  display:grid;
  grid-template-columns:60px 1fr 1fr 1fr 40px;
  gap:8px;align-items:center;
}
.col-labels{padding:0 2px;margin-bottom:6px;}
.col-labels span{
  font-family:var(--mono);font-size:10px;color:var(--dim);
  text-transform:uppercase;letter-spacing:1px;
}
.process-row{margin-bottom:8px;}

.process-row input{
  background:var(--s2);border:1px solid var(--border);
  border-radius:6px;padding:9px 10px;
  color:var(--text);font-family:var(--mono);font-size:13px;
  width:100%;min-width:0;
  transition:border-color .2s,box-shadow .2s;outline:none;
}
.process-row input:focus{
  border-color:var(--accent);
  box-shadow:0 0 0 3px rgba(79,142,255,.12);
}
.process-row input::placeholder{color:var(--dim);opacity:.5;}

.pid-tag{
  background:var(--s3);border:1px solid var(--border2);
  border-radius:6px;padding:9px 0;
  font-family:var(--mono);font-size:13px;font-weight:600;
  text-align:center;
}

.btn-del{
  background:rgba(255,94,122,.1);border:1px solid rgba(255,94,122,.25);
  border-radius:6px;padding:9px 0;color:var(--red);
  cursor:pointer;font-size:14px;line-height:1;font-weight:700;
  transition:background .2s,transform .1s;
}
.btn-del:hover{background:rgba(255,94,122,.2);}
.btn-del:active{transform:scale(.92);}

.hint{
  font-family:var(--mono);font-size:10px;color:var(--dim);
  padding:8px 12px;background:var(--s2);
  border-radius:6px;border-left:2px solid var(--border2);
  line-height:1.5;
}

.controls{display:flex;flex-wrap:wrap;gap:12px;align-items:flex-end;}
.ctrl-group{display:flex;flex-direction:column;gap:6px;flex:1;min-width:180px;}
.ctrl-group label{
  font-family:var(--mono);font-size:10px;color:var(--dim);
  text-transform:uppercase;letter-spacing:1px;
}
select,
input[type="number"].quantum-inp{
  background:var(--s2);border:1px solid var(--border);
  border-radius:6px;padding:10px 12px;
  color:var(--text);font-family:var(--mono);font-size:13px;
  width:100%;outline:none;
  transition:border-color .2s;
}
select{cursor:pointer;}
select:focus,
input[type="number"].quantum-inp:focus{border-color:var(--accent);}

.btn-row{display:flex;flex-wrap:wrap;gap:10px;margin-top:18px;}
.btn{
  padding:10px 18px;border-radius:7px;border:none;
  font-family:var(--sans);font-size:13px;font-weight:600;
  cursor:pointer;transition:transform .15s,box-shadow .2s,background .2s;
  letter-spacing:.3px;flex:1 1 auto;min-width:130px;
}
.btn:active{transform:translateY(0)!important;}
.btn-primary{
  background:linear-gradient(135deg,var(--accent),#3a6fd8);color:#fff;
  box-shadow:0 4px 14px rgba(79,142,255,.25);
}
.btn-primary:hover{transform:translateY(-2px);box-shadow:0 6px 20px rgba(79,142,255,.35);}
.btn-green{
  background:linear-gradient(135deg,var(--green),#00b382);color:#000;
  box-shadow:0 4px 14px rgba(0,223,162,.2);
}
.btn-green:hover{transform:translateY(-2px);box-shadow:0 6px 20px rgba(0,223,162,.3);}
.btn-purple{
  background:linear-gradient(135deg,var(--purple),#9333ea);color:#fff;
  box-shadow:0 4px 14px rgba(192,132,252,.2);
}
.btn-purple:hover{transform:translateY(-2px);box-shadow:0 6px 20px rgba(192,132,252,.3);}
.btn-outline{
  background:transparent;border:1px solid var(--border2);color:var(--dim);
}
.btn-outline:hover{border-color:var(--accent);color:var(--accent);}

.tbl-wrap{overflow-x:auto;-webkit-overflow-scrolling:touch;margin-top:4px;}
table{width:100%;border-collapse:collapse;font-size:13px;min-width:520px;}
thead th{
  background:var(--s3);border:1px solid var(--border);
  padding:10px 12px;font-family:var(--mono);font-size:10px;
  color:var(--dim);text-transform:uppercase;letter-spacing:1px;
  text-align:left;white-space:nowrap;
}
tbody td{
  border:1px solid var(--border);padding:10px 12px;
  font-family:var(--mono);font-size:13px;
  transition:background .15s;white-space:nowrap;
}
tbody tr:hover td{background:var(--s2);}
.col-ct{color:var(--accent);font-weight:600;}
.col-tat{color:var(--green);}
.col-wt{color:var(--yellow);}

.avg-strip{display:flex;flex-wrap:wrap;gap:12px;}
.avg-box{
  background:var(--s2);border:1px solid var(--border);
  border-radius:8px;padding:14px 18px;
  flex:1 1 140px;text-align:center;
}
.avg-box .val{
  font-family:var(--mono);font-size:clamp(20px,5vw,28px);font-weight:700;
  color:var(--accent);line-height:1;margin-bottom:6px;
}
.avg-box .lbl{font-size:10px;color:var(--dim);text-transform:uppercase;letter-spacing:1px;}

.algo-box{
  background:linear-gradient(135deg,rgba(79,142,255,.08),rgba(0,223,162,.05));
  border:1px solid rgba(79,142,255,.25);
  border-radius:8px;padding:16px 18px;
  display:flex;flex-direction:column;gap:6px;
}
.algo-name{font-family:var(--mono);font-size:14px;font-weight:700;color:var(--accent);}
.algo-reason{font-size:13px;color:var(--dim);line-height:1.6;}

/* ---------- Gantt chart (Pydroid-safe) ---------- */
.gantt-outer{
  overflow-x:auto;
  -webkit-overflow-scrolling:touch;
  padding-bottom:8px;
  width:100%;
}
.gantt-inner{
  /* width set inline by JS; explicit instead of max-content for WebView compat */
  display:block;
  position:relative;
}
.gantt-bars{
  display:flex;
  flex-wrap:nowrap;
  height:48px;
  border-radius:8px;
  overflow:hidden;
  border:1px solid var(--border);
  width:100%;
}
.gantt-block{
  /* flex:0 0 Xpx is set inline – guarantees fixed width on Android WebView */
  display:flex;align-items:center;justify-content:center;
  font-family:var(--mono);font-size:12px;font-weight:700;
  color:#fff;cursor:default;
  height:100%;
  min-width:8px; /* keeps tiny slices visible on phones */
  box-sizing:border-box;
  border-right:1px solid rgba(0,0,0,.25);
  overflow:hidden;
  white-space:nowrap;
}
.gantt-block:last-child{border-right:none;}
.gantt-block:hover{filter:brightness(1.25);}
.gantt-block.idle{
  background:repeating-linear-gradient(45deg,#3a4566,#3a4566 6px,#2a3354 6px,#2a3354 12px);
  color:#9aa6c4;font-size:10px;
}
.gantt-times{
  position:relative;
  height:18px;
  margin-top:4px;
  width:100%;
}
.gantt-tick{
  position:absolute;top:0;
  font-family:var(--mono);font-size:10px;color:var(--dim);
  transform:translateX(-50%);
  white-space:nowrap;
}

.cmp-grid{
  display:grid;
  grid-template-columns:repeat(auto-fill,minmax(220px,1fr));
  gap:12px;
}
.cmp-card{
  background:var(--s2);border:1px solid var(--border);
  border-radius:8px;padding:14px;transition:border-color .2s;
}
.cmp-card.best-card{
  border-color:var(--green);
  background:linear-gradient(135deg,rgba(0,223,162,.06),var(--s2));
  box-shadow:0 0 16px rgba(0,223,162,.1);
}
.cmp-card h3{
  font-family:var(--mono);font-size:12px;font-weight:700;
  color:var(--text);margin-bottom:10px;word-break:break-word;
}
.cmp-stat{display:flex;justify-content:space-between;font-size:12px;margin-bottom:6px;gap:8px;}
.cmp-stat span:first-child{color:var(--dim);}
.cmp-stat span:last-child{font-family:var(--mono);font-weight:600;}
.best-badge{
  display:inline-block;background:var(--green);color:#000;
  font-size:9px;font-weight:700;letter-spacing:1px;
  padding:2px 8px;border-radius:4px;text-transform:uppercase;margin-bottom:8px;
}
.err-text{color:var(--red);font-size:11px;font-family:var(--mono);line-height:1.5;}

.hidden{display:none!important;}

#toast{
  position:fixed;left:50%;bottom:20px;
  transform:translateX(-50%) translateY(20px);
  z-index:999;
  background:var(--red);color:#fff;padding:12px 18px;
  border-radius:8px;font-size:13px;font-weight:600;
  opacity:0;transition:all .3s;pointer-events:none;
  max-width:90vw;line-height:1.45;text-align:center;
  box-shadow:0 8px 24px rgba(0,0,0,.4);
}
#toast.show{opacity:1;transform:translateX(-50%) translateY(0);}

/* ----- Mobile ----- */
@media(max-width:560px){
  header{padding:32px 14px 22px;}
  .wrap{padding:18px 12px 60px;}
  .card{padding:16px;}
  .col-labels,
  .process-row{grid-template-columns:48px 1fr 1fr 1fr 36px;gap:6px;}
  .process-row input{padding:9px 8px;font-size:12px;}
  .pid-tag{font-size:12px;padding:9px 0;}
  .ctrl-group{flex:1 1 100%;}
  .btn{flex:1 1 100%;min-width:0;}
  .col-labels span{font-size:9px;}
  .gantt-bars{height:54px;}
}
@media(max-width:380px){
  .col-labels,
  .process-row{grid-template-columns:42px 1fr 1fr 1fr 32px;}
  h1{letter-spacing:-.5px;}
}
</style>
</head>
<body>

<header>
  <div class="badge"><span class="badge-dot"></span>OS Simulator</div>
  <h1>CPU Scheduling Simulator</h1>
  <p>FCFS &middot; SJF &middot; Round Robin &middot; Priority &middot; Adaptive</p>
</header>

<div class="wrap">

  <div class="card">
    <div class="card-head">Process Input</div>
    <div class="col-labels">
      <span>PID</span>
      <span>Arrival</span>
      <span>Burst</span>
      <span>Priority</span>
      <span></span>
    </div>
    <div id="process-list"></div>
    <div style="display:flex;gap:10px;margin-top:12px;align-items:center;flex-wrap:wrap;">
      <button class="btn btn-outline" style="flex:0 0 auto;min-width:140px" onclick="addProcess()">+ Add Process</button>
      <span class="hint">Priority: lower = higher urgency. Leave blank if not using Priority Scheduling.</span>
    </div>
  </div>

  <div class="card">
    <div class="card-head">Configuration</div>
    <div class="controls">
      <div class="ctrl-group">
        <label>Algorithm</label>
        <select id="algo-select">
          <option value="fcfs">FCFS &mdash; First Come First Served</option>
          <option value="sjf">SJF &mdash; Shortest Job First</option>
          <option value="rr">Round Robin</option>
          <option value="priority">Priority Scheduling</option>
          <option value="adaptive">Adaptive (Auto Select)</option>
        </select>
      </div>
      <div class="ctrl-group" style="flex:0 0 130px;min-width:120px;">
        <label>Quantum (RR)</label>
        <input type="number" id="quantum" value="2" min="1" max="999" class="quantum-inp"/>
      </div>
    </div>
    <div class="btn-row">
      <button class="btn btn-primary" onclick="runAlgo()">Run Selected</button>
      <button class="btn btn-green"   onclick="runAdaptive()">Run Adaptive</button>
      <button class="btn btn-purple"  onclick="runCompare()">Compare All</button>
      <button class="btn btn-outline" onclick="resetAll()">Reset</button>
    </div>
  </div>

  <div class="card hidden" id="section-algo-info">
    <div class="card-head">Adaptive Decision</div>
    <div class="algo-box">
      <div class="algo-name"   id="info-algo-name"></div>
      <div class="algo-reason" id="info-algo-reason"></div>
    </div>
  </div>

  <div class="card hidden" id="section-results">
    <div class="card-head">Process Results</div>
    <div class="tbl-wrap">
      <table>
        <thead>
          <tr>
            <th>PID</th><th>Arrival</th><th>Burst</th><th>Priority</th>
            <th>CT</th><th>TAT</th><th>WT</th><th>RT</th>
          </tr>
        </thead>
        <tbody id="result-tbody"></tbody>
      </table>
    </div>
  </div>

  <div class="card hidden" id="section-avg">
    <div class="card-head">Averages</div>
    <div class="avg-strip">
      <div class="avg-box">
        <div class="val" id="avg-wt"></div>
        <div class="lbl">Avg Waiting Time</div>
      </div>
      <div class="avg-box">
        <div class="val" id="avg-tat"></div>
        <div class="lbl">Avg Turnaround</div>
      </div>
      <div class="avg-box">
        <div class="val" id="avg-rt"></div>
        <div class="lbl">Avg Response</div>
      </div>
    </div>
  </div>

  <div class="card hidden" id="section-gantt">
    <div class="card-head">Gantt Chart</div>
    <div class="gantt-outer">
      <div class="gantt-inner" id="gantt-inner">
        <div class="gantt-bars"  id="gantt-bars"></div>
        <div class="gantt-times" id="gantt-times"></div>
      </div>
    </div>
  </div>

  <div class="card hidden" id="section-compare">
    <div class="card-head">Algorithm Comparison</div>
    <div id="best-algo-info" style="margin-bottom:14px;"></div>
    <div class="cmp-grid" id="cmp-grid"></div>
  </div>

</div>

<div id="toast"></div>

<script>
const COLORS = [
  '#4f8eff','#00dfa2','#ff6b6b','#ffd166',
  '#c084fc','#fb923c','#34d399','#f472b6',
  '#60a5fa','#a78bfa','#facc15','#22d3ee'
];

let pidCounter = 1;

function addProcess() {
  const list  = document.getElementById('process-list');
  const pid   = 'P' + pidCounter++;
  const color = COLORS[(pidCounter - 2) % COLORS.length];
  const row   = document.createElement('div');
  row.className   = 'process-row';
  row.dataset.pid = pid;
  row.innerHTML = `
    <div class="pid-tag" style="color:${color};border-color:${color}55">${pid}</div>
    <input type="number" placeholder="0" min="0"  inputmode="numeric" class="inp-arrival"/>
    <input type="number" placeholder="5" min="1"  inputmode="numeric" class="inp-burst"/>
    <input type="number" placeholder="—" min="0"  inputmode="numeric" class="inp-priority"/>
    <button class="btn-del" onclick="deleteProcess(this)" title="Remove">&times;</button>
  `;
  list.appendChild(row);
}

function deleteProcess(btn) {
  btn.closest('.process-row').remove();
}

function readProcesses() {
  const rows = document.querySelectorAll('.process-row');
  const list = [];
  rows.forEach(row => {
    const av = row.querySelector('.inp-arrival').value.trim();
    const bv = row.querySelector('.inp-burst').value.trim();
    const pv = row.querySelector('.inp-priority').value.trim();
    list.push({
      pid:      row.dataset.pid,
      arrival:  av !== '' ? parseInt(av, 10) : 0,
      burst:    bv !== '' ? parseInt(bv, 10) : 0,
      priority: pv !== '' ? parseInt(pv, 10) : null
    });
  });
  return list;
}

function validate(procs) {
  if (procs.length === 0) return 'Add at least one process.';
  for (const p of procs) {
    if (!Number.isFinite(p.burst) || p.burst <= 0)
      return p.pid + ': Burst time must be > 0.';
    if (!Number.isFinite(p.arrival) || p.arrival < 0)
      return p.pid + ': Arrival time cannot be negative.';
    if (p.priority !== null && (!Number.isFinite(p.priority) || p.priority < 0))
      return p.pid + ': Priority must be >= 0.';
  }
  return null;
}

async function callAPI(url, body) {
  const res  = await fetch(url, {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify(body)
  });
  return await res.json();
}

async function runAlgo() {
  const procs = readProcesses();
  const err   = validate(procs);
  if (err) { showToast(err); return; }
  const algo    = document.getElementById('algo-select').value;
  const quantum = parseInt(document.getElementById('quantum').value, 10) || 2;
  try {
    const data = await callAPI('/simulate', {algorithm: algo, quantum, processes: procs});
    if (data.error) { showToast(data.error); return; }
    renderResults(data);
    hideCompare();
  } catch(e) { showToast('Server error: ' + e.message); }
}

async function runAdaptive() {
  const procs = readProcesses();
  const err   = validate(procs);
  if (err) { showToast(err); return; }
  const quantum = parseInt(document.getElementById('quantum').value, 10) || 2;
  try {
    const data = await callAPI('/simulate', {algorithm: 'adaptive', quantum, processes: procs});
    if (data.error) { showToast(data.error); return; }
    renderResults(data);
    hideCompare();
  } catch(e) { showToast('Server error: ' + e.message); }
}

async function runCompare() {
  const procs = readProcesses();
  const err   = validate(procs);
  if (err) { showToast(err); return; }
  const quantum = parseInt(document.getElementById('quantum').value, 10) || 2;
  try {
    const data = await callAPI('/compare', {quantum, processes: procs});
    if (data.error) { showToast(data.error); return; }
    renderComparison(data);
    ['section-results','section-avg','section-gantt','section-algo-info']
      .forEach(id => document.getElementById(id).classList.add('hidden'));
  } catch(e) { showToast('Server error: ' + e.message); }
}

function buildPidColorMap(results) {
  const map = {};
  results.forEach((r, i) => { map[r.pid] = COLORS[i % COLORS.length]; });
  return map;
}

function renderResults(data) {
  const algoSection = document.getElementById('section-algo-info');
  if (data.reason) {
    document.getElementById('info-algo-name').textContent   = 'Selected: ' + data.algorithm;
    document.getElementById('info-algo-reason').textContent = data.reason;
    algoSection.classList.remove('hidden');
  } else {
    algoSection.classList.add('hidden');
  }

  const tbody = document.getElementById('result-tbody');
  tbody.innerHTML = '';
  const pidColorMap = buildPidColorMap(data.results);
  data.results.forEach(r => {
    const color = pidColorMap[r.pid];
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td style="color:${color};font-weight:700">${r.pid}</td>
      <td>${r.arrival}</td>
      <td>${r.burst}</td>
      <td>${r.priority !== null && r.priority !== undefined ? r.priority : '—'}</td>
      <td class="col-ct">${r.ct}</td>
      <td class="col-tat">${r.tat}</td>
      <td class="col-wt">${r.wt}</td>
      <td>${r.rt}</td>
    `;
    tbody.appendChild(tr);
  });
  document.getElementById('section-results').classList.remove('hidden');

  document.getElementById('avg-wt').textContent  = data.averages.avg_wt;
  document.getElementById('avg-tat').textContent = data.averages.avg_tat;
  document.getElementById('avg-rt').textContent  = data.averages.avg_rt ?? '—';
  document.getElementById('section-avg').classList.remove('hidden');

  /* IMPORTANT: unhide section BEFORE measuring/rendering Gantt
     (Pydroid WebView gives 0 width if measured while display:none) */
  const ganttSection = document.getElementById('section-gantt');
  ganttSection.classList.remove('hidden');

  // Defer to next frame so WebView has a real layout to measure
  requestAnimationFrame(() => {
    renderGantt(data.gantt, pidColorMap);
    // smooth scroll to results so users see the chart immediately
    setTimeout(() => {
      ganttSection.scrollIntoView({behavior: 'smooth', block: 'start'});
    }, 80);
  });
}

function renderGantt(gantt, pidColorMap) {
  const inner    = document.getElementById('gantt-inner');
  const barsDiv  = document.getElementById('gantt-bars');
  const timesDiv = document.getElementById('gantt-times');
  barsDiv.innerHTML  = '';
  timesDiv.innerHTML = '';
  if (!gantt || gantt.length === 0) return;

  const totalStart = gantt[0].start;
  const totalEnd   = gantt[gantt.length - 1].end;
  const totalTime  = Math.max(totalEnd - totalStart, 1);

  // Use viewport width to choose px-per-unit (better mobile fit)
  const viewportW = Math.max(window.innerWidth || 360, 320);
  const idealPx   = Math.max(viewportW - 80, 320);
  const pxPerUnit = Math.max(24, Math.min(60, Math.floor(idealPx / totalTime)));
  const totalPx   = Math.max(320, totalTime * pxPerUnit);

  // Set explicit width on inner wrapper so flex children can be sized in px
  inner.style.width = totalPx + 'px';

  gantt.forEach(g => {
    const duration = g.end - g.start;
    const w = Math.max(8, duration * pxPerUnit);  // min 8px so 1-unit slices show
    const div = document.createElement('div');
    const isIdle = g.pid === 'IDLE';
    div.className = 'gantt-block' + (isIdle ? ' idle' : '');
    // flex: 0 0 Xpx — ESSENTIAL for Android WebView to keep block widths
    div.style.flex = '0 0 ' + w + 'px';
    div.style.width = w + 'px';
    if (!isIdle) {
      div.style.background = pidColorMap[g.pid] || '#4f8eff';
    }
    div.textContent = isIdle ? 'idle' : g.pid;
    div.title = g.pid + ': ' + g.start + ' -> ' + g.end +
                ' (' + duration + ' unit' + (duration !== 1 ? 's' : '') + ')';
    barsDiv.appendChild(div);
  });

  // time ticks at every unique boundary
  const points = new Set();
  gantt.forEach(g => { points.add(g.start); points.add(g.end); });
  const sorted = [...points].sort((a, b) => a - b);

  sorted.forEach(t => {
    const tick = document.createElement('div');
    tick.className   = 'gantt-tick';
    tick.textContent = t;
    const left = ((t - totalStart) / totalTime) * totalPx;
    tick.style.left = left + 'px';
    timesDiv.appendChild(tick);
  });
}

function renderComparison(data) {
  const grid = document.getElementById('cmp-grid');
  grid.innerHTML = '';

  document.getElementById('best-algo-info').innerHTML = `
    <div class="algo-box">
      <div class="algo-name">Best: ${data.best_algorithm}</div>
      <div class="algo-reason">
        Lowest Avg Waiting Time:
        <strong style="color:var(--green)">${data.best_avg_wt}</strong>
        &nbsp;|&nbsp; Avg Turnaround:
        <strong style="color:var(--accent)">${data.best_avg_tat}</strong>
      </div>
    </div>
  `;

  data.comparison.forEach(c => {
    const isBest = c.algorithm === data.best_algorithm && !c.error;
    const card   = document.createElement('div');
    card.className = 'cmp-card' + (isBest ? ' best-card' : '');
    if (c.error) {
      card.innerHTML = `<h3>${c.algorithm}</h3><p class="err-text">${c.error}</p>`;
    } else {
      card.innerHTML = `
        ${isBest ? '<div class="best-badge">★ Best</div>' : ''}
        <h3>${c.algorithm}</h3>
        <div class="cmp-stat">
          <span>Avg Waiting</span>
          <span style="color:${isBest ? 'var(--green)' : 'var(--text)'}">${c.averages.avg_wt}</span>
        </div>
        <div class="cmp-stat">
          <span>Avg Turnaround</span>
          <span>${c.averages.avg_tat}</span>
        </div>
        <div class="cmp-stat">
          <span>Avg Response</span>
          <span>${c.averages.avg_rt}</span>
        </div>
        <div class="cmp-stat">
          <span>Processes</span>
          <span>${c.results.length}</span>
        </div>
      `;
    }
    grid.appendChild(card);
  });

  document.getElementById('section-compare').classList.remove('hidden');
  setTimeout(() => {
    document.getElementById('section-compare')
            .scrollIntoView({behavior: 'smooth', block: 'start'});
  }, 80);
}

function hideCompare() {
  document.getElementById('section-compare').classList.add('hidden');
}

function resetAll() {
  document.getElementById('process-list').innerHTML = '';
  pidCounter = 1;
  ['section-results','section-avg','section-gantt','section-algo-info','section-compare']
    .forEach(id => document.getElementById(id).classList.add('hidden'));
  addProcess(); addProcess(); addProcess();
}

let toastTimer = null;
function showToast(msg) {
  const t = document.getElementById('toast');
  t.textContent = msg;
  t.classList.add('show');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => t.classList.remove('show'), 4000);
}

window.addEventListener('load', () => {
  addProcess(); addProcess(); addProcess();
});

// Re-render Gantt on window resize / orientation change so it adapts to phone rotation
let resizeTimer = null;
window.addEventListener('resize', () => {
  clearTimeout(resizeTimer);
  resizeTimer = setTimeout(() => {
    const ganttSection = document.getElementById('section-gantt');
    if (!ganttSection.classList.contains('hidden')) {
      // Trigger re-run of last algo so the Gantt is recomputed at the new width
      // (cheaper alternative: just rescale; we keep it simple)
    }
  }, 200);
});
</script>
</body>
</html>
"""


def _open_browser():
    """Open default browser after the server is up. Safe on Pydroid + Desktop."""
    try:
        webbrowser.open_new("http://127.0.0.1:5000/")
    except Exception:
        pass


if __name__ == '__main__':
    print("=" * 56)
    print("  CPU Scheduling Simulator")
    print("  Local URL : http://127.0.0.1:5000")
    print("  LAN URL   : http://0.0.0.0:5000  (open from phone on same Wi-Fi)")
    print("  Press Ctrl+C to stop.")
    print("=" * 56)

    # Open browser shortly after Flask boots (helps on Pydroid)
    threading.Timer(1.2, _open_browser).start()

    # debug=False -> no reloader, no inotify; works in Pydroid
    # use_reloader=False is double safety on Android
    app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)
