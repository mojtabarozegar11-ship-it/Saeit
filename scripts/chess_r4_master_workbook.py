#!/usr/bin/env python3
"""Chess R4: source-verified game scores, annotated positions and independent problems."""
import re,io,os,json,hashlib,html,statistics
from pathlib import Path
import chess,chess.pgn,chess.engine
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import SimpleDocTemplate,Paragraph,PageBreak,Flowable,KeepTogether
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import A4
root=Path(__file__).resolve().parents[1]
out=Path('chess_r4_build');out.mkdir(exist_ok=True)
src=(root/'catalog/mojplaywin/chess_research/100_sourced_game_scores.md').read_text()
tick=chr(96)*3
blocks=re.findall(re.escape(tick)+r'pgn\s*\n(.*?)\n'+re.escape(tick),src,re.S|re.I)
if len(blocks)!=100:raise RuntimeError('SOURCE_SCORE_COUNT:'+str(len(blocks)))
games=[];invalid=[]
for i,pgn in enumerate(blocks,1):
 g=chess.pgn.read_game(io.StringIO(pgn))
 if not g or g.errors:invalid.append((i,str(g.errors[:2]) if g else 'null'));continue
 b=g.board();positions=[];san=[]
 for m in g.mainline_moves():
  if m not in b.legal_moves:invalid.append((i,m.uci()));break
  positions.append((b.copy(stack=False),m,b.san(m)));san.append(b.san(m));b.push(m)
 else:
  if len(san)>=14:games.append({'num':i,'headers':dict(g.headers),'positions':positions,'san':san,'comments':[]})
  else:invalid.append((i,'short game'))
if len(games)!=100:raise RuntimeError('SCORE_LEGALITY_FAILURE:'+str(invalid))
engine=chess.engine.SimpleEngine.popen_uci('/usr/games/stockfish')
engine.configure({'Threads':1,'Hash':32})
eid=dict(engine.id); seen=set(); allcases=[]; depths=[]
def choose_indices(n):
 lo=min(13,n-4);hi=n-3
 arr=[int(lo+(hi-lo)*q) for q in (.17,.51,.82)]
 for i in range(1,3):
  if arr[i]<=arr[i-1]:arr[i]=arr[i-1]+1
 return arr
def formatted(board,line):
 try:return board.variation_san(line[:8])
 except Exception:return ' '.join(m.uci() for m in line[:8])
def unique_key(b):
 return ' '.join(b.fen().split()[:4])
def teaching(b,played,top,second):
 vals={chess.PAWN:1,chess.KNIGHT:3,chess.BISHOP:3.25,chess.ROOK:5,chess.QUEEN:9}
 w=sum(len(b.pieces(k,chess.WHITE))*val for k,val in vals.items())
 bl=sum(len(b.pieces(k,chess.BLACK))*val for k,val in vals.items())
 checks=sum(b.gives_check(m) for m in b.legal_moves)
 caps=sum(b.is_capture(m) for m in b.legal_moves)
 move=b.san(played); lead=b.san(top['line'][0])
 secondmove=b.san(second['line'][0]) if second else 'not available'
 intro=f'The recorded game move is {move}; the engine first candidate is {lead}, and the runner-up is {secondmove}. '
 concrete=f'White has {w:.2f} material units, Black has {bl:.2f}, with {checks} available checks and {caps} immediate captures. '
 nature='checking' if b.gives_check(top['line'][0]) else 'capturing' if b.is_capture(top['line'][0]) else 'quiet'
 exp=f'The leading candidate is a {nature} move. '
 if lead==move:exp+='Here the historical choice agrees with the short engine search. '
 else:exp+='The historical choice differs from the first candidate at this search budget; this alone does not demonstrate a blunder. '
 if second:
  gap=top['cp']-second['cp']
  if gap>125:exp+=f'The displayed alternatives differ by {gap/100:.2f} pawn units. Find the concrete reply that creates this gap before forming a verdict. '
  elif gap>35:exp+=f'The engine candidate gap is approximately {gap/100:.2f} pawn units; move order and defensive resources deserve verification. '
  else:exp+='The candidates are close in provisional evaluation and may both be playable. '
 return intro+concrete+exp+'To make the conclusion reproducible, start from the FEN and test the strongest opponent defense.'
try:
 for gi,g in enumerate(games,1):
  ps=g['positions'];indices=choose_indices(len(ps))
  for k in indices:
   b,m,msan=ps[k]
   if unique_key(b) in seen:
    alt=[x for x in range(max(5,k-8),min(len(ps),k+8)) if unique_key(ps[x][0]) not in seen]
    if not alt:raise RuntimeError('No unique position for game '+str(gi))
    k=min(alt,key=lambda x:abs(x-k));b,m,msan=ps[k]
   seen.add(unique_key(b))
   infos=engine.analyse(b,chess.engine.Limit(time=.18),multipv=2)
   opts=[]
   for info in infos[:2]:
    pv=info.get('pv',[])
    if not pv:continue
    sc=info['score'].pov(b.turn)
    opts.append({'line':pv,'cp':sc.score(mate_score=100000),'mate':sc.mate(),'depth':info.get('depth',0)})
   if not opts:raise RuntimeError('Engine empty PV')
   top=opts[0];other=opts[1] if len(opts)>1 else None
   depths.append(top['depth'])
   item={'id':len(allcases)+1,'game':gi,'fen':b.fen(),'side':'White' if b.turn else 'Black',
     'ply':k+1,'played':msan,'best':b.san(top['line'][0]),
     'runner':b.san(other['line'][0]) if other else 'not available',
     'pv':formatted(b,top['line']),'second_pv':formatted(b,other['line']) if other else 'not available',
     'cp':top['cp'],'mate':top['mate'],'depth':top['depth'],
     'second_cp':other['cp'] if other else None,'comment':teaching(b,m,top,other)}
   g['comments'].append(item);allcases.append(item)
  print('CHESS_GAME_VERIFIED',gi,len(ps),flush=True)
finally:engine.quit()
exercises=[c for g in games for c in (g['comments'][0],g['comments'][2])]
assert len(allcases)==300 and len(exercises)==200 and len({unique_key(chess.Board(c['fen'])) for c in exercises})==200
font='/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf';bold='/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'
pdfmetrics.registerFont(TTFont('DV',font));pdfmetrics.registerFont(TTFont('DV-B',bold))
st={'title':ParagraphStyle('title',fontName='DV-B',fontSize=18,leading=25,textColor=HexColor('#163F4D'),spaceAfter=11),
    'h':ParagraphStyle('h',fontName='DV-B',fontSize=10.8,leading=15.2,textColor=HexColor('#1A6477'),spaceBefore=10,spaceAfter=6),
    'p':ParagraphStyle('p',fontName='DV',fontSize=8.1,leading=12.8,spaceAfter=7),
    'small':ParagraphStyle('small',fontName='DV',fontSize=7.1,leading=11,spaceAfter=6,textColor=HexColor('#4E6570'))}
def P(text,typ='p'):return Paragraph(html.escape(str(text)),st[typ])
class BoardDiagram(Flowable):
 def __init__(self,fen,size=162):Flowable.__init__(self);self.b=chess.Board(fen);self.sz=size;self.width=size+24;self.height=size+20
 def draw(self):
  c=self.canv;u=self.sz/8
  for r in range(8):
   for f in range(8):
    col='#E9DFCE' if (r+f)%2==0 else '#86A9A0'
    c.setFillColor(HexColor(col));c.rect(20+f*u,12+(7-r)*u,u,u,stroke=0,fill=1)
    piece=self.b.piece_at(chess.square(f,7-r))
    if piece:
     blk=piece.color==chess.BLACK
     c.setFillColor(HexColor('#123844' if blk else '#FFF7E6'))
     c.circle(20+(f+.5)*u,12+(7-r+.5)*u,u*.39,stroke=0,fill=1)
     c.setFillColor(HexColor('#FFFFFF' if blk else '#133B49'))
     c.setFont('DV-B',u*.48)
     c.drawCentredString(20+(f+.5)*u,12+(7-r+.5)*u-u*.17,piece.symbol().upper())
  c.setFillColor(HexColor('#45616E'));c.setFont('DV',7)
  for f in range(8):c.drawCentredString(20+(f+.5)*u,2,'abcdefgh'[f])
  for r in range(8):c.drawRightString(16,12+(r+.45)*u,str(r+1))
def page(c,d):
 c.saveState();c.setFont('DV',7);c.setFillColor(HexColor('#2A6D7A'))
 c.drawString(43,A4[1]-28,'MOJPLAYWIN | GRANDMASTER-LEVEL RESEARCH | R4')
 c.drawRightString(A4[0]-42,25,str(d.page));c.restoreState()
story=[P('One Hundred Game Studies & Two Hundred Independent Decision Exercises','title'),
       P('Research supplement for The Science and Practice of Chess Improvement | Author and researcher: Mojtaba Roozegar | 2026'),
       P('Scientific limits: Game scores are legal source records. The 300 candidate evaluations are Stockfish snapshots at 0.18 seconds per position with MultiPV=2, not 300 formally proven best moves. The 200 puzzles are distinct board-state decision exercises, not necessarily forced tactical wins. Human grandmaster review has not occurred.'),
       P('Source credit: https://github.com/brianerdelyi/ChessPGN. Only move scores and header facts are processed; no historical commentary is copied. Historical event/date attribution requires a separate cross-check.','small'),PageBreak(),P('Part I: 100 real-game decision studies','title')]
for g in games:
 h=g['headers'];story.append(P(f"Game {g['num']:03d}: {h.get('White','?')} vs {h.get('Black','?')}",'h'))
 story.append(P(f"Event {h.get('Event','?')} | Date {h.get('Date','?')} | Result {h.get('Result','?')} | {len(g['san'])} legal half-moves",'small'))
 pairs=[str(i//2+1)+'. '+g['san'][i]+(' '+g['san'][i+1] if i+1<len(g['san']) else '') for i in range(0,len(g['san']),2)]
 story.append(P('Complete source game (SAN): '+' '.join(pairs),'small'))
 for j,x in enumerate(g['comments'],1):
  story.append(P(f"Critical position {j}: {x['side']} to move, source ply {x['ply']}",'h'))
  story.append(P(x['comment']))
  story.append(P(f"FEN: {x['fen']}",'small'))
  story.append(P(f"Variation A: {x['pv']} | Variation B: {x['second_pv']}",'small'))
 story.append(PageBreak())
story.extend([P('Part II: 200 independent practice positions','title'),
 P('Record two candidates and the strongest defensive reply before reading the answer key. The exercises are two separate genuine historical positions from each game. Multiple playable moves may exist; do not confuse a short search lead with a forced solution.','small')])
for i,x in enumerate(exercises,1):
 story.append(P(f"Exercise {i:03d}: {x['side']} to move | Game {x['game']:03d}",'h'))
 story.append(BoardDiagram(x['fen']))
 story.append(P('Tasks: identify a candidate, name a serious alternative, calculate opponent counterplay, and assess uncertainty.','small'))
 story.append(P('FEN: '+x['fen'],'small'))
 if i%2==0:story.append(PageBreak())
story.extend([P('Part III: worked, evidence-limited answers','title'),
              P('These evaluations are reproducible exploratory Stockfish observations, not proof of uniqueness or human grandmaster certification.','small')])
for i,x in enumerate(exercises,1):
 score=('mate '+str(x['mate'])) if x['mate'] is not None else ('%+.2f'%(x['cp']/100) if x['cp'] is not None else 'unknown')
 story.append(P(f"Answer {i:03d}: {x['best']} | evaluation {score} | depth {x['depth']}",'h'))
 story.append(P(x['comment']))
 story.append(P(f"Variation A: {x['pv']} | Variation B: {x['second_pv']}",'small'))
 story.append(P('FEN: '+x['fen'],'small'))
story.extend([P('Editorial and release limitations','h'),P('The source has 100 legal score records; there are 300 unique engine-reviewed board states and 200 independent practice positions. This does not demonstrate 100 deep human-edited game analyses, engine proof of all alternatives, 150,000 nonduplicated useful words, or full rights clearance. These require further work before public sales.')])
pdf=out/'MojPlayWin_Chess_R4_100_Games_200_Exercises.pdf'
SimpleDocTemplate(str(pdf),pagesize=A4,leftMargin=43,rightMargin=43,topMargin=47,bottomMargin=40,title='MojPlayWin R4 Game and Exercise Research Workbook',author='Mojtaba Roozegar').build(story,onFirstPage=page,onLaterPages=page)
from pypdf import PdfReader
pages=len(PdfReader(str(pdf)).pages)
qa={'release':'R4','legal_source_games':len(games),'bad_game_scores':invalid,
    'position_analyses':len(allcases),'unique_positions':len(seen),
    'independent_exercises':len(exercises),'exercise_unique_positions':len({unique_key(chess.Board(c['fen'])) for c in exercises}),
    'engine_id':eid,'engine_time_sec_per_position':.18,'multipv':2,
    'min_depth':min(depths),'max_depth':max(depths),'average_depth':round(statistics.mean(depths),1),
    'pages':pages,'sha256':hashlib.sha256(pdf.read_bytes()).hexdigest(),
    'human_grandmaster_reviewed':False,'deep_verified_100_games':False,
    'all_150000_words_distinct_quality_verified':False,'commercial_release_approved':False}
(out/'MojPlayWin_Chess_R4_QA.json').write_text(json.dumps(qa,indent=2,ensure_ascii=False))
(out/'MojPlayWin_Chess_R4_Editorial_Status.md').write_text('# R4 editorial status\n\n'+
 f"Legal games: {len(games)}/100. Distinct analyzed positions: {len(allcases)}. Unique exercises: {len(exercises)}. PDF pages: {pages}. Engine: {eid}. Depth range: {min(depths)}-{max(depths)}.\n\n"+
 'Game facts sourced from https://github.com/brianerdelyi/ChessPGN; no third-party commentary included. Analysis is original algorithm-assisted teaching commentary, based on 0.18-second searches, not adjudicated master-level depth. R3 and storefront remain unchanged. Further historical provenance, rights and human specialist review required.\n')
print('R4_COMPLETE',json.dumps({k:v for k,v in qa.items() if k!='bad_game_scores'}),flush=True)
