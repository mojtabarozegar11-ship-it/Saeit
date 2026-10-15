#!/usr/bin/env python3
"""Standalone R2 engine audit: no site code, database, network or credentials."""
import json,sys,hashlib
import chess,chess.engine
FENS=["q5nr/1ppknQpp/3p4/1P2p3/4P3/B1PP1b2/B5PP/5K2 w - - 1 18","3r4/ppk2pp1/2p1p3/4b3/P3n1P1/8/KPP2PN1/3rBR1R w - - 3 32","8/8/3pk3/8/3PK3/8/8/8 w - - 0 1","8/8/4k3/1p6/8/4K3/P7/8 w - - 0 1","4k3/8/8/2p5/8/8/5PP1/4K2R w - - 0 1","8/2k5/p7/8/8/7P/6K1/8 w - - 0 1","4k3/1p6/8/8/3P4/8/4K3/4R3 w - - 0 1","4k3/4p3/2p5/1p6/8/2N5/4P3/4K3 w - - 0 1","4k3/8/4p3/2p1P3/8/2P5/4B3/4K3 w - - 0 1","4k3/3p4/8/8/3P4/8/4K3/7R w - - 0 1","8/8/2k5/p7/P1K5/8/8/8 w - - 0 1","4k3/1p3pp1/p7/8/2P5/8/PP3PP1/4K3 w - - 0 1","r3r1k1/p4ppp/2p2n2/1p6/3P1qb1/2NQ2R1/PPB2PP1/R1B3K1 b - - 6 18","Q1b2r1k/p2Rp2p/5bp1/q7/5P2/4B3/PPP3PP/2K2B1R b - - 0 17"]
LINES=[[0,"a2e6","d7d8","f7f8"],[1,"e1a5","b7b6","f1d1"],[12,"e8e1","g1h2","e1c1","a1c1","f4h6","h2g1","h6c1"],[13,"a5e1","d7d1","e1e3","c1b1","e3b6"]]
assert len(set(FENS))==14
engine=chess.engine.SimpleEngine.popen_uci("/usr/games/stockfish")
out=[]
try:
  print("CHESS_ENGINE_ID",json.dumps(engine.id))
  for i,fen in enumerate(FENS,1):
    b=chess.Board(fen)
    if not b.is_valid(): raise RuntimeError("Invalid game state at case "+str(i))
    infos=engine.analyse(b,chess.engine.Limit(time=0.3),multipv=2)
    score=[]
    for info in infos:
      pv=info.get("pv",[])
      score.append({"score_cp_current_side":info["score"].pov(b.turn).score(mate_score=100000),
                    "mate":info["score"].pov(b.turn).mate(),
                    "depth":info.get("depth"),"pv_uci":[m.uci() for m in pv[:9]]})
    row={"case":i,"fen":fen,"legal_moves":b.legal_moves.count(),"engine":score}
    out.append(row)
    print("CHESS_RESULT",json.dumps(row,separators=(",",":")))
  for idx,*moves in LINES:
    b=chess.Board(FENS[idx])
    for u in moves:
      m=chess.Move.from_uci(u)
      assert m in b.legal_moves,(idx,u,b.fen())
      b.push(m)
    print("CHESS_SOURCE_LINE",idx+1,"legal",True,"checkmate",b.is_checkmate(),"final_fen",b.fen())
  with open("chess_r2_engine_result.json","w") as f:
    json.dump({"engine":engine.id,"method":"Stockfish 0.3s per position multipv 2, dynamic depth; exploratory, not a forced-best-move proof","cases":out},f,indent=2)
finally:
  engine.quit()
