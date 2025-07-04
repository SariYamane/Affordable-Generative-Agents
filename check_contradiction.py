import argparse, glob, json, os, pathlib, re, datetime as dt, pandas as pd

def parse_args():
    p = argparse.ArgumentParser(
        description="ルールベース矛盾チェッカ（movement*.json 用）"
    )
    # movement ディレクトリを 1 個以上受け取る
    p.add_argument(
        "mov_dirs",
        nargs="+",
        help="movement/*.json が格納されたディレクトリ（複数指定可）"
    )
    # 必要なら LEGAL テーブルの外部ファイルもオプション化
    p.add_argument("--legal_json", type=str, help="合法遷移テーブル（JSON）")
    return p.parse_args()

def parse_snapshot(path):
    with open(path, encoding="utf-8") as fp:
        d = json.load(fp)

    try:
        ts = dt.datetime.strptime(d["meta"]["curr_time"], "%B %d, %Y, %H:%M:%S")
    except ValueError:
        ts = dt.datetime.strptime(d["meta"]["curr_time"], "%B %d, %Y, %H:%M")

    recs = []
    for subj, info in d["persona"].items():
        # ---- ここで description を取り出して変数に ----
        description = info.get("description", "")

        # 「@」以降が場所。<persona> などはスキップ
        if "@" in description and not description.lstrip().startswith("<persona>"):
            loc = description.split("@", 1)[-1].strip()
            recs.append((ts, subj, "is_in", loc))

    return recs

def main():
    args = parse_args()
    
    records = []
    for mov_path in args.mov_dirs:
        # ディレクトリなら *.json を補完、ワイルドカードならそのまま
        if os.path.isdir(mov_path):
            pattern = os.path.join(mov_path.rstrip("/\\"), "*.json")
        else:
            pattern = mov_path

        for p in glob.glob(pattern):          # 必要なら , recursive=True
            records.extend(parse_snapshot(p))

    df = pd.DataFrame(records, columns=["ts", "subj", "pred", "obj"]).sort_values("ts")

    print(f"総レコード数 : {len(df)}")                    # 全行数
    print("\npredicate 内訳:\n", df["pred"].value_counts())  # pred 列の頻度
    print("\n先頭10行:\n", df.head(10).to_string(index=False))  # 中身をざっと確認

    # LEGAL テーブルを外部 JSON から読む場合
    if args.legal_json:
        with open(args.legal_json, encoding="utf-8") as f:
            LEGAL = json.load(f)
    else:
        LEGAL = {
            "state": {
                "destroyed": {"destroyed"},
                "intact": {"intact", "destroyed"},
            },
            "is_in": {},
            "is_in": {"*": {"*"}},
        }

    # ---- 矛盾検出：同一タイムスタンプ内で同一人物が複数ロケ ----
    dup_idx = (df.groupby(["ts", "subj"])["obj"]
                 .nunique()
                 .reset_index()
                 .query("obj > 1"))

    contradictions = dup_idx.to_dict("records")

    total, n_con = len(df), len(contradictions)
    rate = 100 * n_con / total if total else 0
    print(f"contradiction_count  : {n_con}")
    print(f"contradiction_rate_% : {rate:.2f}")

if __name__ == "__main__":
    main()
