# -*- coding: utf-8 -*-
import statistics, logging
from dataclasses import dataclass
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta

from ..db import Database

logger = logging.getLogger(__name__)

@dataclass
class GrowthMetrics:
    channel_id: int
    period_days: int
    view_growth: float
    subscriber_growth: float
    video_count_growth: int
    engagement_rate: float
    growth_score: float
    trend: str

@dataclass
class ChannelSnapshot:
    channel_id: int
    date: str
    subscriber_count: int
    view_count: int
    video_count: int
    avg_view_per_video: float

class GrowthService:
    def __init__(self, db: Database):
        self.db = db

    def _get_snapshots(self, channel_id: int, days: int) -> List[ChannelSnapshot]:
        end = datetime.now(); start = end - timedelta(days=days)
        rows = self.db.query("""
            SELECT channel_id, date, 
                   COALESCE(NULL,(SELECT subs FROM channels WHERE channel_id=?)) as subscriber_count,
                   view_count, 
                   COALESCE(NULL,(SELECT videos FROM channels WHERE channel_id=?)) as video_count
            FROM video_snapshots 
            WHERE channel_id=? AND date BETWEEN ? AND ?
            ORDER BY date ASC
        """, (channel_id, channel_id, channel_id, start.strftime('%Y-%m-%d'), end.strftime('%Y-%m-%d')))
        out=[]
        for r in rows:
            vc = r[3]
            vn = r[4] if r[4] else 1
            out.append(ChannelSnapshot(
                channel_id=r[0], date=r[1],
                subscriber_count=r[2] if r[2] else 0,
                view_count=vc if vc else 0,
                video_count=vn if vn else 0,
                avg_view_per_video=(vc or 0)/max((vn or 1),1)
            ))
        return out

    @staticmethod
    def _growth(a:int,b:int)->float:
        if a==0: return 0.0
        return (b-a)*100.0/a

    def _engagement(self, channel_id:int, days:int)->float:
        # proxy: 最新30日 snapshots の like/view 平均（view_count>0）
        rows = self.db.query("""
            SELECT AVG(CAST(like_count AS FLOAT) / NULLIF(CAST(view_count AS FLOAT),0)) * 100.0
            FROM video_snapshots
            WHERE channel_id=? AND date >= date('now', ?) AND view_count>0
        """, (channel_id, f"-{days} days"))
        if not rows or rows[0][0] is None: return 0.0
        return float(rows[0][0])

    def analyze(self, channel_id:int, days:int=30)->Optional[GrowthMetrics]:
        snaps=self._get_snapshots(channel_id, days)
        if len(snaps)<2: 
            logger.warning(f"Insufficient snapshots for channel {channel_id}")
            return None
        view_g = self._growth(snaps[0].view_count, snaps[-1].view_count)
        # subs は channels テーブルからの補助データなので 0 になる可能性あり
        sub_g = self._growth(snaps[0].subscriber_count, snaps[-1].subscriber_count)
        video_g = snaps[-1].video_count - snaps[0].video_count
        engagement = self._engagement(channel_id, days)

        # スコア
        view_score = max(min(view_g, 100), -100)
        sub_score  = max(min(sub_g, 100), -100)
        video_score = min(video_g*10, 100)
        engagement_score = min(engagement*10, 100)
        total = view_score*0.3 + sub_score*0.3 + video_score*0.2 + engagement_score*0.2
        overall = max(0, min(100, total + 50))

        # トレンド（最後の3点で簡易）
        if len(snaps)>=3:
            gr=[]
            for i in range(1,3):
                a=snaps[-(i+1)].view_count; b=snaps[-i].view_count
                gr.append(self._growth(a,b))
            avg = statistics.mean(gr)
            trend = "rising" if avg>5 else ("declining" if avg<-5 else "stable")
        else:
            trend="unknown"

        return GrowthMetrics(channel_id, days, view_g, sub_g, video_g, engagement, overall, trend)

    def top_growing(self, limit:int=10, days:int=30):
        rows=self.db.query("""
            SELECT DISTINCT channel_id 
            FROM video_snapshots 
            WHERE date >= date('now', ?)
            ORDER BY channel_id
        """, (f"-{days} days",))
        results=[]
        for r in rows:
            m=self.analyze(r[0], days)
            if m: results.append(m)
        results.sort(key=lambda x: x.growth_score, reverse=True)
        return results[:limit]
