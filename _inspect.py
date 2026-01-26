import sqlite3 
db=sqlite3.connect('b:/Graph_Pivot/Graph_Pivot/backend/data/app.db') 
cur=db.cursor() 
cur.execute('select chapter_id,start_char,end_char,title from chapters where book_id=? order by order_index',('b_853bfbd76a8a4defb380a1435a89356f',)) 
rows=cur.fetchall() 
path='b:/Graph_Pivot/Graph_Pivot/backend/data/books/b_853bfbd76a8a4defb380a1435a89356f/source.pages.md' 
data=open(path,'r',encoding='utf-8',errors='ignore').read() 
print('chapters',len(rows)) 
for r in rows[:8]: 
    cid,start,end,title=r 
    chunk=data[start:end] 
    print(cid,start,end,len(chunk.strip()),title)
