import urllib.request

# DB 파일 없으면 GitHub LFS에서 직접 다운로드
if not os.path.exists(DB_PATH):
    print("DB 파일 다운로드 중...")
    lfs_url = "https://media.githubusercontent.com/media/leejaeyung0-ui/ddareungi-analysis/main/ljy_ddareungi.db"
    urllib.request.urlretrieve(lfs_url, DB_PATH)
    print("DB 파일 다운로드 완료!")

from flask import Flask, jsonify, request, send_from_directory
import sqlite3
import os

app = Flask(__name__, static_folder='static')
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'ljy_ddareungi.db')

# DB 파일 존재 여부 확인
if not os.path.exists(DB_PATH):
    print(f"DB 파일 없음: {DB_PATH}")
    print(f"현재 폴더 파일 목록: {os.listdir(os.path.dirname(DB_PATH))}")

def query_db(sql, args=()):
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    cur = con.execute(sql, args)
    rows = [dict(r) for r in cur.fetchall()]
    con.close()
    return rows

# ── 메인 페이지 ──────────────────────────────
@app.route('/')
def index():
    return send_from_directory('static', 'index.html')

# ── 필터 API ─────────────────────────────────
@app.route('/api/filter')
def api_filter():
    month  = request.args.get('month',  'all')
    gender = request.args.get('gender', 'all')
    age    = request.args.get('age',    'all')
    rent   = request.args.get('rent',   'all')

    where  = []
    params = []

    if month  != 'all': where.append("month = ?");       params.append(month)
    if gender != 'all': where.append("gender = ?");      params.append(gender)
    if age    != 'all': where.append("age_group = ?");   params.append(age)
    if rent   != 'all': where.append("rent_simple = ?"); params.append(rent)

    w = ("WHERE " + " AND ".join(where)) if where else ""

    # 월별 집계
    monthly = query_db(f"""
        SELECT month, SUM(use_count) as count
        FROM bike_clean {w} GROUP BY month ORDER BY month
    """, params)

    # 성별 집계
    gender_data = query_db(f"""
        SELECT gender, SUM(use_count) as count
        FROM bike_clean {w} GROUP BY gender
    """, params)

    # 연령대 집계
    age_data = query_db(f"""
        SELECT age_group, SUM(use_count) as count
        FROM bike_clean {w} GROUP BY age_group ORDER BY count DESC
    """, params)

    # 대여구분 집계
    rent_data = query_db(f"""
        SELECT rent_simple, SUM(use_count) as count
        FROM bike_clean {w} GROUP BY rent_simple
    """, params)

    # 연령대별 평균 이동거리/이용시간
    avg_data = query_db(f"""
        SELECT age_group,
               ROUND(AVG(distance_km), 2) as avg_distance,
               ROUND(AVG(use_time_min), 1) as avg_time
        FROM bike_clean {w}
        GROUP BY age_group ORDER BY age_group
    """, params)

    # KPI
    kpi = query_db(f"""
        SELECT SUM(use_count) as total_count,
               ROUND(AVG(distance_km), 2) as avg_distance,
               ROUND(AVG(use_time_min), 1) as avg_time,
               COUNT(*) as combo_count
        FROM bike_clean {w}
    """, params)

    # 이동거리 구간 집계
    dist_bin = query_db(f"""
        SELECT
            CASE
                WHEN distance_km < 2  THEN '0-2km'
                WHEN distance_km < 5  THEN '2-5km'
                WHEN distance_km < 10 THEN '5-10km'
                ELSE '10km+'
            END as range,
            COUNT(*) as count
        FROM bike_clean {w}
        WHERE distance_km IS NOT NULL
        GROUP BY range
    """, params)

    return jsonify({
        'kpi':      kpi[0] if kpi else {},
        'monthly':  monthly,
        'gender':   gender_data,
        'age':      age_data,
        'rent':     rent_data,
        'avg':      avg_data,
        'dist_bin': dist_bin,
    })

# ── 분석결과 API (고정) ────────────────────────
@app.route('/api/analysis')
def api_analysis():
    # 군집 결과
    cluster = query_db("""
        SELECT cluster,
               ROUND(AVG(distance_km), 2)   as avg_distance,
               ROUND(AVG(use_time_min), 1)  as avg_time,
               ROUND(AVG(use_count), 1)     as avg_count,
               COUNT(*) as cnt
        FROM bike_cluster GROUP BY cluster ORDER BY avg_distance
    """)

    # KNN 정확도
    knn = query_db("""
        SELECT
            SUM(CASE WHEN 실제 = 예측 THEN 1 ELSE 0 END) * 100.0 / COUNT(*) as accuracy,
            COUNT(*) as total
        FROM bike_knn_result
    """)

    return jsonify({
        'cluster': cluster,
        'knn':     knn[0] if knn else {}
    })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
