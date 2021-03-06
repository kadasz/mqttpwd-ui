#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import asyncio
import aiohttp_jinja2
from settings import NAME, ht
from utils import run_process
from aiohttp.web  import Response, HTTPFound, json_response
from aiohttp_security import remember, forget, authorized_userid


async def validate_login(form):
    error = None

    username = form['username']
    password = form['password']

    cur_user = ht.users()
    if not username in cur_user:
        ht.set_password(username, password)
        ht.save()
        error = None
    if username in cur_user and not ht.check_password(username, password):
        error = 'Not valid password'
    return dict(error=error, user=f'{cur_user[0]}' if cur_user else username)


def redirect(router, route_name):
    location = router[route_name].url_for()
    return HTTPFound(location)

@aiohttp_jinja2.template('index.html')
async def index(request):
    auth = await authorized_userid(request)
    if not auth:
        if not ht.users():
            request.app['register'] = 'register'
            raise redirect(request.app.router, 'login')
        elif 'admin' in ht.users():
            request.app['register'] = None
            raise redirect(request.app.router, 'login')
    else:
        return dict(
            title=NAME,
            username=auth,
            users=await _getUsers(request)
        )

async def logout(request):
    request.app['register'] = None
    response = redirect(request.app.router, 'login')
    await forget(request, response)
    return response

@aiohttp_jinja2.template('login.html')
async def login(request):
    if request.method == 'POST':
        form = await request.post()
        is_validate = await validate_login(form)
        if is_validate.get('error'):
            return {'error': is_validate.get('error')}
        else:
            user = is_validate.get('user')
            response = redirect(request.app.router, 'index')
            request['user'] = user
            await remember(request, response, user)
            raise response

async def uptime(request):
    auth = await authorized_userid(request)
    if not auth:
        raise redirect(request.app.router, 'login')
    elif auth:
        data = await run_process('uptime')
        return Response(text=data)

async def pwdchange(request):
    auth = await authorized_userid(request)
    if not auth:
        raise redirect(request.app.router, 'login')
    elif auth :
        data = await request.json()
        user = data.get('user', None)
        newpass = data.get('pwd', None)
        if user == 'admin' and newpass:
            ht.set_password("admin", newpass)
            ht.save()
            return json_response({'status_admin': 'Admin password has changed. Please logout and sign in again'})
        elif user and newpass:
            change_pwd = await run_process(f'mosquitto_passwd -b {request.app["pwd"]} {user} {newpass}')
            return json_response({'status_user': f'User {user} password has updated'})
        else:
            return json_response({'status': 'Something went wrong'})

async def ucreate(request):
    auth = await authorized_userid(request)
    if not auth:
        raise redirect(request.app.router, 'login')
    elif auth :
        form = await request.json()
        user = form['user']
        passwd = form['pwd']
        cur_users = await _getUsers(request)
        if user in cur_users:
            return json_response({'status': 'exists'})
        elif user and passwd:
            create_user = await run_process(f'mosquitto_passwd -b {request.app["pwd"]} {user} {passwd}')
            return json_response({'status': 'created'})
        else:
            return json_response({'status': 'False'})

async def udelete(request):
    auth = await authorized_userid(request)
    if not auth:
        raise redirect(request.app.router, 'login')
    elif auth :
        form = await request.json()
        user = form['user']
        cur_users = await _getUsers(request)
        if user in cur_users:
            delete_user = await run_process(f'mosquitto_passwd -D {request.app["pwd"]} {user}')
            return json_response({'status': 'deleted'})
        else:
            return json_response({'status': 'False'})
            
            

async def _getUsers(request):
    with open(request.app['pwd']) as htpwd:
        usernames = [line.split(":")[0] for line in htpwd.readlines()]
    return usernames
