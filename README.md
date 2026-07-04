# コンサドーレ情報ボード (ローカル版)

ブラウザの制約を受けずに、ニュースと日程・結果をWebからリアルタイム取得する
Streamlitアプリです。資産管理ツールと同じ Python + Streamlit 構成です。

## セットアップ(初回のみ)

```bash
cd consadole-app
pip install -r requirements.txt
```

## 起動

```bash
streamlit run app.py
```

ブラウザが自動で開きます(http://localhost:8501)。

## データの仕組み

| タブ | データ源 | 更新 |
|---|---|---|
| ニュース | Google News RSS(キー不要・安定) | 5分ごと自動+「今すぐ更新」ボタン |
| 日程・結果 | クラブ公式サイト(失敗時は7/4時点の確定日程に自動フォールバック) | 同上 |
| 記録・クラブ | アプリ内蔵の固定データ | - |

## Claude Codeで育てる

このフォルダで `claude` を起動して、次のように頼めば改良できます:

- 「日程のスクレイピングが公式サイトの構造変更で動かなくなったので直して」
- 「順位表タブを追加して。J2の順位をJリーグ公式から取得」
- 「試合結果をCSVに蓄積して、得失点の推移グラフを出して」
- 「動作確認: `python fetchers.py` で取得テストができます」

## ファイル構成

```
consadole-app/
├── app.py          # Streamlit画面
├── fetchers.py     # ニュース・日程の取得ロジック(単体テスト可)
├── requirements.txt
└── README.md
```
