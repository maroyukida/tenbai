# -*- coding: utf-8 -*-
import os, json, logging, re
from dataclasses import dataclass
from typing import Dict, List, Optional, Any
from datetime import datetime
import requests

from ..db import Database

logger = logging.getLogger(__name__)

@dataclass
class BanInfo:
    channel_name: str
    channel_url: Optional[str]
    ban_date: Optional[str]
    description: str
    reason: str
    category: Optional[str]
    severity: Optional[str]
    scraped_at: str

class BanClassifier:
    """ルール + LLM(DeepSeek) で BAN 理由を分類"""
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.environ.get("DEEPSEEK_API_KEY")
        self.endpoint = "https://api.deepseek.com/v1/chat/completions"
        self.categories = {
            'copyright': ['著作権', 'コピー', '無断転載', '盗用'],
            'harassment': ['嫌がらせ', 'いじめ', '誹謗中傷', 'ハラスメント'],
            'hate_speech': ['ヘイト', '差別', '暴言', '人種'],
            'violence': ['暴力', '殺害', '武器', '危険'],
            'adult_content': ['アダルト', '性的', '不適切', '18禁'],
            'spam': ['スパム', '宣伝', '詐欺', 'bot'],
            'misinformation': ['誤情報', 'デマ', '陰謀論', 'フェイク'],
            'terms_violation': ['規約違反', 'ガイドライン', 'ポリシー'],
            'other': ['その他', '不明', '詳細不明']
        }

    def classify(self, description: str, reason: str = "") -> Dict[str, Any]:
        # ルールベース優先
        rb = self._rule_based(description, reason)
        if rb["confidence"] > 0.8 or not self.api_key:
            return rb
        # LLM 推論
        ai = self._ai_based(description, reason)
        return ai or rb

    def _rule_based(self, description: str, reason: str) -> Dict[str, Any]:
        text = f"{description} {reason}".lower()
        matched = []
        scores = {}
        for cat, kws in self.categories.items():
            s=0
            for kw in kws:
                if kw.lower() in text:
                    s += 1; matched.append(kw)
            scores[cat]=s
        best = max(scores, key=scores.get)
        conf = min(scores[best]/3.0, 1.0) if scores[best] > 0 else 0.1
        return {"category": best, "confidence": conf, "reasoning": f"Keyword: {matched[:3]}", "keywords": matched[:5]}

    def _ai_based(self, description: str, reason: str) -> Optional[Dict[str, Any]]:
        try:
            headers = {'Authorization': f'Bearer {self.api_key}', 'Content-Type': 'application/json'}
            prompt = f"""
以下のYouTubeチャンネルBAN情報を分類してください。JSONのみ返答。

説明: {description}
既知理由: {reason}

カテゴリ:
- copyright, harassment, hate_speech, violence, adult_content, spam, misinformation, terms_violation, other
"""
            payload = {'model': 'deepseek-chat', 'messages': [{'role':'user','content':prompt}], 'temperature':0.1, 'max_tokens':400}
            r = requests.post(self.endpoint, json=payload, headers=headers, timeout=30)
            if r.status_code==200:
                content = r.json()['choices'][0]['message']['content']
                m=re.search(r'\{.*\}', content, re.S)
                if m:
                    return json.loads(m.group())
        except Exception as e:
            logger.warning(f"AI classify failed: {e}")
        return None

class BanService:
    def __init__(self, db: Database):
        self.db = db
        self.classifier = BanClassifier()

    def save_ban(self, info: BanInfo, classification: Dict[str, Any]):
        self.db.execute("""
            INSERT INTO ban_channels (channel_name, channel_url, ban_date, description, reason, category, severity, scraped_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (info.channel_name, info.channel_url, info.ban_date, info.description, info.reason, classification.get("category"), info.severity, info.scraped_at))
        self.db.execute("""
            INSERT INTO ban_reasons (channel_name, category, confidence, reasoning, keywords, classified_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (info.channel_name, classification.get("category"), classification.get("confidence"), classification.get("reasoning",""), json.dumps(classification.get("keywords",[])), datetime.now().isoformat()))

    def determine_severity(self, classification: Dict[str, Any]) -> str:
        cat = classification.get("category","other"); conf = float(classification.get("confidence") or 0.0)
        if cat in {"copyright","harassment","hate_speech","violence"} and conf>0.7: return "high"
        if conf>0.5: return "medium"
        return "low"
