# -*- coding: utf-8 -*-
import time
from sqlite3 import dbapi2 as sqlite3
from hashlib import md5
from datetime import datetime
from flask import Flask, request, session, url_for, redirect, \
     render_template, abort, g, flash, _app_ctx_stack
from werkzeug.security import check_password_hash, generate_password_hash
import time

#CONFIGURATION
DATABASE = 'book.db'
DEBUG = True
SECRET_KEY = 'development key'
MANAGER_NAME = 'admin'
MANAGER_PWD = '123456'

app = Flask(__name__)

app.config.from_object(__name__)
app.config.from_envvar('FLASKR_SETTINGS', silent=True)


def get_db():
    top = _app_ctx_stack.top
    if not hasattr(top, 'sqlite_db'):
        top.sqlite_db = sqlite3.connect(app.config['DATABASE'])
        top.sqlite_db.row_factory = sqlite3.Row
    return top.sqlite_db

@app.teardown_appcontext
def close_database(exception):
    top = _app_ctx_stack.top
    if hasattr(top, 'sqlite_db'):
        top.sqlite_db.close()

def init_db():
    with app.app_context():
        db = get_db()
        try:
            # 方法1：使用标准Python方式打开文件
            with open('book.sql', 'r', encoding='utf-8') as f:
                db.cursor().executescript(f.read())
            
            # 或者方法2：使用 pathlib（更现代）
            # from pathlib import Path
            # sql_content = Path('book.sql').read_text(encoding='utf-8')
            # db.cursor().executescript(sql_content)
            
            db.commit()
            print("✅ 数据库初始化成功！")
            
        except FileNotFoundError:
            print("❌ 错误：找不到 book.sql 文件")
            return
        except Exception as e:
            print(f"❌ 数据库初始化失败：{e}")
            return

def query_db(query, args=(), one=False):
    cur = get_db().execute(query, args)
    rv = cur.fetchall()
    return (rv[0] if rv else None) if one else rv


def get_user_id(username):
    rv = query_db('select user_id from users where user_name = ?',
                  [username], one=True)
    return rv[0] if rv else None


@app.before_request
def before_request():
    g.user = None
    if 'user_id' in session:
        g.user = session['user_id']

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/manager_login', methods=['GET', 'POST'])
def manager_login():
    error = None
    if request.method == 'POST':
        if request.form['username'] != app.config['MANAGER_NAME']:
            error = 'Invalid username'
        elif request.form['password'] != app.config['MANAGER_PWD']:
            error = 'Invalid password'
        else:
            session['user_id'] = app.config['MANAGER_NAME']
            return redirect(url_for('manager'))
    return render_template('manager_login.html', error = error)


@app.route('/reader_login', methods=['GET', 'POST'])
def reader_login():
    error = None
    if request.method == 'POST':
        user = query_db('''select * from users where user_name = ?''',
                [request.form['username']], one=True)
        if user is None:
            error = 'Invalid username'
        elif not check_password_hash(user['pwd'], request.form['password']):
            error = 'Invalid password'
        else:
            session['user_id'] = user['user_name']
            return redirect(url_for('reader'))
    return render_template('reader_login.html', error = error)


@app.route('/register', methods=['GET', 'POST'])
def register():
    error = None
    if request.method == 'POST':
        if not request.form['username']:
            error = 'You have to enter a username'
        elif not request.form['password']:
            error = 'You have to enter a password'
        elif request.form['password'] != request.form['password2']:
            error = 'The two passwords do not match'
        elif get_user_id(request.form['username']) is not None:
            error = 'The username is already taken'
        else:
            db = get_db()
            db.execute('''insert into users (user_name, pwd, college, num, email) \
                values (?, ?, ?, ?, ?) ''', [request.form['username'], generate_password_hash(
                request.form['password']), request.form['college'], request.form['number'],
                                 request.form['email']])
            db.commit()
            return redirect(url_for('reader_login'))
    return render_template('register.html', error = error)

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    return redirect(url_for('index'))

# 添加简单的安全性检查
def manager_judge():
    if not session['user_id']:
        error = 'Invalid manager, please login'
        return render_template('manager_login.html', error = error)

def reader_judge():
    if not session['user_id']:
        error = 'Invalid reader, please login'
        return render_template('reader_login.html', error = error)


@app.route('/manager/books')
def manager_books():
    manager_judge()
    
    # 获取搜索参数，默认搜索书名为空，搜索类型为书名
    keyword = request.args.get('keyword', '')
    search_type = request.args.get('search_type', 'book_name')  # 默认按书名
    
    if keyword:
        if search_type == 'book_id':
            books = query_db('''select * from books where book_id like ?''', 
                           [f'%{keyword}%'])
        elif search_type == 'book_name':
            books = query_db('''select * from books where book_name like ?''', 
                           [f'%{keyword}%'])
        elif search_type == 'author':
            books = query_db('''select * from books where author like ?''', 
                           [f'%{keyword}%'])
        else:  # 全部字段
            books = query_db('''select * from books where 
                              book_id like ? or book_name like ? or author like ?''',
                           [f'%{keyword}%', f'%{keyword}%', f'%{keyword}%'])
    else:
        books = query_db('''select * from books''')
    
    return render_template('manager_books.html', 
                         books=books, 
                         keyword=keyword,
                         search_type=search_type)

@app.route('/manager')
def manager():
    manager_judge()
    return render_template('manager.html')

@app.route('/reader')
def reader():
    reader_judge()
    return render_template('reader.html')

@app.route('/manager/users')
def manager_users():
    manager_judge()
    users = query_db('''select * from users''', [])
    return render_template('manager_users.html', users = users)

@app.route('/manager/user/modify/<id>', methods=['GET', 'POST'])
def manger_user_modify(id):
    manager_judge()
    error = None
    user = query_db('''select * from users where user_id = ?''', [id], one=True)
    if request.method == 'POST':
        if not request.form['username']:
            error = 'You have to input your name'
        elif not request.form['password']:
            db = get_db()
            db.execute('''update users set user_name=?, college=?, num=? \
                , email=? where user_id=? ''', [request.form['username'],
                request.form['college'], request.form['number'],
                request.form['email'], id])
            db.commit()
            return redirect(url_for('manager_user', id = id))
        else:
            db = get_db()
            db.execute('''update users set user_name=?, pwd=?, college=?, num=? \
                , email=? where user_id=? ''', [request.form['username'],
                    generate_password_hash(request.form['password']),
                request.form['college'], request.form['number'],
                request.form['email'], id])
            db.commit()
            return redirect(url_for('manager_user', id = id))
    return render_template('manager_user_modify.html', user=user, error = error)

@app.route('/manager/user/deleter/<id>', methods=['GET', 'POST'])
def manger_user_delete(id):
    manager_judge()
    db = get_db()
    db.execute('''delete from users where user_id=? ''', [id])
    db.commit()
    return redirect(url_for('manager_users'))


@app.route('/manager/books/add', methods=['GET', 'POST'])
def manager_books_add():
    manager_judge()
    error = None
    if request.method == 'POST':
        if not request.form['id']:
            error = 'You have to input the book ISBN'
        elif not request.form['name']:
            error = 'You have to input the book name'
        elif not request.form['author']:
            error = 'You have to input the book author'
        elif not request.form['company']:
            error = 'You have to input the publish company'
        elif not request.form['date']:
            error = 'You have to input the publish date'
        else:
            db = get_db()
            db.execute('''insert into books (book_id, book_name, author, publish_com,
                publish_date) values (?, ?, ?, ?, ?) ''', [request.form['id'],
                    request.form['name'], request.form['author'], request.form['company'],
                request.form['date']])
            db.commit()
            return redirect(url_for('manager_books'))
    return render_template('manager_books_add.html', error = error)

@app.route('/manager/books/delete', methods=['GET', 'POST'])
def manager_books_delete():
    manager_judge()
    error = None
    if request.method == 'POST':
        if not request.form['id']:
            error = 'You have to input the book name'
        else:
            book = query_db('''select * from books where book_id = ?''',
                [request.form['id']], one=True)
            if book is None:
                error = 'Invalid book id'
            else:
                db = get_db()
                db.execute('''delete from books where book_id=? ''', [request.form['id']])
                db.commit()
                return redirect(url_for('manager_books'))
    return render_template('manager_books_delete.html', error = error)

@app.route('/manager/book/<int:id>', methods=['GET', 'POST'])
def manager_book(id):
    manager_judge()
    
    book = query_db('''select * from books where book_id = ?''', [id], one=True)
    if not book:
        return "图书不存在", 404
    
    reader = query_db('''select * from borrows where book_id = ?''', [id], one=True)
    
    # 处理还书请求
    if request.method == 'POST':
        if request.form.get('action') == 'return' and reader:
            current_time = time.strftime('%Y-%m-%d', time.localtime(time.time()))
            db = get_db()
            
            # 更新历史记录
            db.execute('''update histroys 
                          set status = ?, date_return = ?  
                          where book_id=? and user_name=?''',
                       ['returned', current_time, id, reader['user_name']])
            
            # 从借阅表中删除
            db.execute('''delete from borrows where book_id = ?''', [id])
            db.commit()
            
            flash('图书归还成功！')
            return redirect(url_for('manager_book', id=id))
    
    return render_template('manager_book.html', book=book, reader=reader)
@app.route('/manager/user/<id>', methods=['GET', 'POST'])
def manager_user(id):
    manager_judge()
    user = query_db('''select * from users where user_id = ?''', [id], one=True)
    books = None
    return render_template('manager_userinfo.html', user = user, books = books)


@app.route('/manager/modify/<id>', methods=['GET', 'POST'])
def manager_modify(id):
    manager_judge()
    error = None
    book = query_db('''select * from books where book_id = ?''', [id], one=True)
    if request.method == 'POST':
        if not request.form['name']:
            error = 'You have to input the book name'
        elif not request.form['author']:
            error = 'You have to input the book author'
        elif not request.form['company']:
            error = 'You have to input the publish company'
        elif not request.form['date']:
            error = 'You have to input the publish date'
        else:
            db = get_db()
            db.execute('''update books set book_name=?, author=?, publish_com=?, publish_date=? where book_id=? ''', [request.form['name'], request.form['author'], request.form['company'], request.form['date'], id])
            db.commit()
            return redirect(url_for('manager_book', id = id))
    return render_template('manager_modify.html', book = book, error = error)

@app.route('/reader/info', methods=['GET', 'POST'])
def reader_info():
    reader_judge()
    user = query_db('''select * from users where user_name=? ''', [g.user], one = True)
    return render_template('reader_info.html', user = user)


@app.route('/reader/modify', methods=['GET', 'POST'])
def reader_modify():
    reader_judge()
    error = None
    user = query_db('''select * from users where user_name = ?''', [g.user], one=True)
    id = user[0]
    if request.method == 'POST':
        if not request.form['username']:
            error = 'You have to input your name'
        elif not request.form['password']:
            db = get_db()
            db.execute('''update users set user_name=?, college=?, num=? \
                , email=? where user_id=? ''', [request.form['username'],
                request.form['college'], request.form['number'],
                request.form['email'], id])
            db.commit()
            return redirect(url_for('reader_info'))
        else:
            db = get_db()
            db.execute('''update users set user_name=?, pwd=?, college=?, num=? \
                , email=? where user_id=? ''', [request.form['username'],
                    generate_password_hash(request.form['password']),
                request.form['college'], request.form['number'],
                request.form['email'], id])
            db.commit()
            return redirect(url_for('reader_info'))
    return render_template('reader_modify.html', user=user, error = error)


@app.route('/reader/query', methods=['GET', 'POST'])
def reader_query():
    reader_judge()
    error = None
    books = None
    
    if request.method == 'POST':
        # 获取表单数据
        query_key = request.form.get('query', '').strip()  # 模板中是 name="query"
        item = request.form.get('item', 'name')            # 模板中是 name="item"
        
        print(f"=== 调试信息 ===")
        print(f"查询关键词: '{query_key}'")
        print(f"查询类型: '{item}'")
        
        if not query_key:
            error = '请输入查询关键词'
        else:
            if item == 'name':  # 按书名查询
                # 使用模糊查询 LIKE 和 % 通配符
                books = query_db('''select * from books where book_name like ?''',
                        [f'%{query_key}%'])  # 关键：添加 % 进行模糊匹配
                
                if not books:
                    error = f'未找到包含 "{query_key}" 的图书'
                    
            else:  # item == 'author'，按作者查询
                # 使用模糊查询 LIKE 和 % 通配符
                books = query_db('''select * from books where author like ?''',
                        [f'%{query_key}%'])  # 关键：添加 % 进行模糊匹配
                
                if not books:
                    error = f'未找到作者包含 "{query_key}" 的图书'
            
            print(f"查询到 {len(books) if books else 0} 条记录")
    
    return render_template('reader_query.html', books=books, error=error)


@app.route('/reader/book/<id>', methods=['GET', 'POST'])
def reader_book(id):
    """读者查看图书详情并借书（修复版）"""
    reader_judge()
    
    error = None
    book = query_db('''select * from books where book_id = ?''', [id], one=True)
    
    if not book:
        return "图书不存在", 404
    
    reader = query_db('''select * from borrows where book_id = ?''', [id], one=True)
    count = query_db('''select count(book_id) from borrows where user_name = ?''',
                     [g.user], one=True)
    
    # 处理借书请求（POST）
    if request.method == 'POST':
        if reader:
            error = '该书已被借阅！'
        else:
            if count and count[0] >= 3:  # 检查借阅数量限制
                error = '每人最多只能借阅3本书！'
            else:
                current_time = time.strftime('%Y-%m-%d', time.localtime(time.time()))
                return_time = time.strftime('%Y-%m-%d', time.localtime(time.time() + 2600000))
                
                db = get_db()
                try:
                    # 1. 添加到借阅表
                    db.execute('''insert into borrows (user_name, book_id, date_borrow, date_return) 
                                  values (?, ?, ?, ?)''', 
                               [g.user, id, current_time, return_time])
                    
                    # 2. 添加到历史记录表
                    db.execute('''insert into histroys (user_name, book_id, date_borrow, status) 
                                  values (?, ?, ?, ?)''', 
                               [g.user, id, current_time, 'borrowed'])
                    
                    db.commit()
                    flash('借书成功！', 'success')
                    return redirect(url_for('reader_book', id=id))
                    
                except Exception as e:
                    db.rollback()
                    error = f'借书失败：{str(e)}'
    
    # ✅ 统一返回：无论是GET请求还是POST请求（有错误时）
    return render_template('reader_book.html', book=book, reader=reader, error=error)

@app.route('/reader/histroy', methods=['GET', 'POST'])
def reader_histroy():
    reader_judge()
    histroys = query_db('''select * from histroys, books where histroys.book_id = books.book_id and histroys.user_name=? ''', [g.user], one = False)

    return render_template('reader_histroy.html', histroys = histroys)


@app.route('/book/borrow/<int:id>', methods=['POST'])
def borrow_book(id):
    """管理员借书功能"""
    manager_judge()
    
    # 获取借阅者姓名
    user_name = request.form.get('user_name', '').strip()
    if not user_name:
        flash('请输入借阅者姓名！', 'error')
        return redirect(url_for('manager_book', id=id))
    
    # 查询图书信息
    book = query_db('''select * from books where book_id = ?''', [id], one=True)
    if not book:
        flash('图书不存在！', 'error')
        return redirect(url_for('manager_books'))
    
    # 检查是否已被借阅
    borrowed = query_db('''select * from borrows where book_id = ?''', [id], one=True)
    if borrowed:
        flash('该书已被借阅！', 'error')
        return redirect(url_for('manager_book', id=id))
    
    # 计算借阅日期和应还日期
    current_time = time.strftime('%Y-%m-%d', time.localtime(time.time()))
    return_date = time.strftime('%Y-%m-%d', 
                               time.localtime(time.time() + 30*24*3600))  # 30天后
    
    db = get_db()
    try:
        # 1. 添加到借阅表
        db.execute('''insert into borrows (book_id, user_name, date_borrow, date_return) 
                      values (?, ?, ?, ?)''',
                   [id, user_name, current_time, return_date])
        
        # 2. 添加到历史记录表（注意：表名是 histroys，可能是拼写错误，应该是 histories）
        db.execute('''insert into histroys (book_id, user_name, date_borrow, status) 
                      values (?, ?, ?, ?)''',
                   [id, user_name, current_time, 'borrowed'])
        
        db.commit()
        flash(f'成功借阅《{book["book_name"]}》给 {user_name}', 'success')
        
    except Exception as e:
        db.rollback()
        flash(f'借阅失败：{str(e)}', 'error')
    
    return redirect(url_for('manager_book', id=id))





if __name__ == '__main__':
    init_db()
    app.run(debug=True)


