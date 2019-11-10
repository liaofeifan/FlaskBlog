import os
import random
from functools import wraps
import click
from flask import Flask, render_template, request, redirect, url_for, session, flash, make_response
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from passlib.hash import sha256_crypt
from wtforms import StringField, validators, PasswordField, TextAreaField
from flask_wtf import FlaskForm
from faker import Faker  # 用于生成虚拟数据

from wtforms.validators import DataRequired, ValidationError

app = Flask(__name__)
project_dir = os.path.dirname(os.path.abspath(__file__))
database_file = "sqlite:///{}".format(os.path.join(project_dir, "data.db"))
app.config['SQLALCHEMY_DATABASE_URI'] = database_file
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SESSION_TYPE'] = 'filesystem'
app.config['SECRET_KEY'] = 'the random string'

db = SQLAlchemy(app)

fake = Faker("zh_CN")


class BlogPost(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(50))
    subtitle = db.Column(db.String(50))
    author = db.Column(db.String(20))
    date_posted = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    content = db.Column(db.Text)


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50))
    username = db.Column(db.String(50))
    email = db.Column(db.String(100))
    password = db.Column(db.String(100))
    register_date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)


# 用户注册表单类
class RegisterForm(FlaskForm):
    name = StringField('Name', [validators.Length(min=1, max=50)])
    username = StringField('UserName', [validators.Length(min=4, max=25)])
    email = StringField('Email', [validators.Length(min=6, max=50)])
    password = PasswordField('Password', [validators.DataRequired(), validators.EqualTo(
        'confirm', message='Passwords do not match')])
    confirm = PasswordField('Confirm Password')

    # 校验用户名是否重复
    def validate_username(self, username):
        user = User.query.filter_by(username=username.data).first()
        if user is not None:
            raise ValidationError('用户名重复了，请您重新换一个!')

    # 校验邮箱是否重复
    def validate_email(self, email):
        user = User.query.filter_by(email=email.data).first()
        if user is not None:
            raise ValidationError('邮箱重复了，请您重新换一个!')


# 博客表单类
class BlogForm(FlaskForm):
    title = StringField('Title', [validators.Length(min=1, max=200)])
    subtitle = StringField('SubTitle', [validators.Length(min=1, max=200)])
    author = StringField('Author', [validators.Length(min=1, max=50)])
    content = TextAreaField('Content', [validators.Length(min=1)])


# 用户主页页面
@app.route('/register', methods=['GET', 'POST'])
def register():
    form = RegisterForm()
    if form.validate_on_submit():
        name = form.name.data
        email = form.email.data
        username = form.username.data
        password = sha256_crypt.encrypt(str(form.password.data))
        # 增加用户
        newUser = User(name=name, email=email, username=username, password=password)
        db.session.add(newUser)
        db.session.commit()
        flash('You are now registered and can log in', 'success')
        return redirect(url_for('login'))
    return render_template('register.html', form=form)


# 用户登录处理
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        # 获取表单字段
        username = request.form['username']
        password_candidate = request.form['password']

        # 根据用户名查询用户
        result = User.query.filter(User.username == username)

        if result.count() > 0:
            # 查询第一条数据，并获取密码字段
            data = result.first()
            password = data.password
            # 比较密码字段是否相等
            if sha256_crypt.verify(password_candidate, password):
                # Passed
                session['logged_in'] = True
                session['username'] = username
                flash('You are now logged in', 'success')
                return redirect(url_for('dashboard'))
            else:
                error = 'Invalid login'
                return render_template('login.html', error=error)
        else:
            error = 'Username not found'
            return render_template('login.html', error=error)

    return render_template('login.html')


# 检查用户是否已经登录系统，这里采用的是装饰器函数
def is_logged_in(f):
    @wraps(f)
    def wrap(*args, **kwargs):
        if 'logged_in' in session:
            return f(*args, **kwargs)
        else:
            flash('Unauthorized: Please log in', 'danger')
            return redirect(url_for('login'))

    return wrap


# 博客列表页面
@app.route('/dashboard')
@is_logged_in
def dashboard():
    result = BlogPost.query.all()
    if result:
        return render_template('dashboard.html', Blogs=result)
    else:
        msg = 'NO Blogs Found'
        render_template('dashboard.html', a=msg)
    return render_template('dashboard.html')


# 注销登录
@app.route('/logout')
def logout():
    session.clear()
    flash('You are now logged out', 'success')
    return render_template('login.html')


# 默认首页
@app.route('/')
def index():
    posts = BlogPost.query.order_by(BlogPost.date_posted.desc()).all()

    return render_template('index.html', posts=posts)


# 关于页面
@app.route('/about')
def about():
    return render_template('about.html')


# 博客显示页面
@app.route('/post/<int:post_id>')
def post(post_id):
    post = BlogPost.query.filter_by(id=post_id).one()
    return render_template('post.html', post=post)


# 增加博客文章处理
@app.route('/add_blog', methods=['GET', 'POST'])
@is_logged_in
def add_blog():
    form = BlogForm()
    if form.validate_on_submit():
        title = form.title.data
        subtitle = form.subtitle.data
        author = form.author.data
        content = form.content.data
        newpost = BlogPost(title=title, subtitle=subtitle, author=author, content=content, date_posted=datetime.now())
        db.session.add(newpost)
        db.session.commit()
        flash('Article Created', 'success')
        return redirect(url_for('dashboard'))
    return render_template('add_blog.html', form=form)


@app.route('/save_blog', methods=['POST'])
@is_logged_in
def save_blog():
    form = BlogForm()
    if form.validate_on_submit():
        title = form.title.data
        subtitle = form.subtitle.data
        author = form.author.data
        content = form.content.data

        post = BlogPost(title=title, subtitle=subtitle, author=author, content=content, date_posted=datetime.now())
        db.session.add(post)
        db.session.commit()
        flash('Article Created', 'success')
        return redirect(url_for('dashboard'))
    return render_template('add_blog.html', form=form)


# 便捷博客处理
@app.route('/edit_blog/<int:id>', methods=['GET', 'POST'])
@is_logged_in
def edit_blog(id):
    blog = BlogPost.query.get_or_404(id)
    form = BlogForm()
    if form.validate_on_submit():
        title = request.form['title']
        subtitle = request.form['subtitle']
        author = request.form['author']
        content = request.form['content']
        blog.title = title
        blog.subtitle = subtitle
        blog.author = author
        blog.content = content
        blog.date_posted = datetime.now()
        db.session.commit()
        flash('Blog Updated', 'success')
        return redirect(url_for('dashboard'))
    elif request.method == 'GET':
        form.title.data = blog.title
        form.subtitle.data = blog.subtitle
        form.author.data = blog.author
        form.content.data = blog.content
    else:
        pass
    return render_template('/edit_blog.html', form=form)


# 删除博客处理
@app.route('/delete_blog/<int:id>', methods=['GET'])
@is_logged_in
def delete_blog(id):
    blog = BlogPost.query.get_or_404(id)
    try:
        db.session.delete(blog)
        db.session.commit()
    except:
        return "There was a problem deleting data."
    return redirect(url_for("dashboard"))


# 利用flask initdb初始化数据库
@app.cli.command()
def initdb():
    db.create_all()
    click.echo('Initialized database.')


# 利用flask dropdb初始化数据库
@app.cli.command()
def dropdb():
    db.drop_all()
    click.echo('dropped database.')


# 利用flask fakerdb初始化数据库
@app.cli.command()
def fakerdb():
    fake_posts(50)
    click.echo('faker database.')


# 生成假数据便于测试
def fake_posts(count=50):
    for i in range(count):
        post = BlogPost(
            title=fake.sentence(),
            subtitle=fake.sentence(),
            content=fake.text(2000),
            author=fake.name(),
            date_posted=fake.date_time_this_year()
        )

        db.session.add(post)
    db.session.commit()


# 生成随机文件名
def gen_rnd_filename():
    filename_prefix = datetime.now().strftime('%Y%m%d%H%M%S')
    return '%s%s' % (filename_prefix, str(random.randrange(1000, 10000)))


# 处理图片上传请求
@app.route('/ckupload/', methods=['POST'])
def ckupload():
    """CKEditor file upload"""
    error = ''
    url = ''
    callback = request.args.get("CKEditorFuncNum")
    if request.method == 'POST' and 'upload' in request.files:
        fileobj = request.files['upload']
        fname, fext = os.path.splitext(fileobj.filename)
        rnd_name = '%s%s' % (gen_rnd_filename(), fext)
        filepath = os.path.join(app.static_folder, 'upload', rnd_name)
        # 检查路径是否存在，不存在则创建
        dirname = os.path.dirname(filepath)
        if not os.path.exists(dirname):
            try:
                os.makedirs(dirname)
            except:
                error = 'ERROR_CREATE_DIR'
        elif not os.access(dirname, os.W_OK):
            error = 'ERROR_DIR_NOT_WRITEABLE'
        if not error:
            fileobj.save(filepath)
            url = url_for('static', filename='%s/%s' % ('upload', rnd_name))
    else:
        error = 'post error'
    res = """<script type="text/javascript">
  window.parent.CKEDITOR.tools.callFunction(%s, '%s', '%s');
</script>""" % (callback, url, error)
    response = make_response(res)
    response.headers["Content-Type"] = "text/html"
    return response


if __name__ == '__main__':
    app.run(debug=True)
