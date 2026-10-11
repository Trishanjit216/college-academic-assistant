import React, {useState} from 'react';
import axios from 'axios';
import { useNavigate } from 'react-router-dom';
import { Container, TextField, Button, Typography } from '@mui/material';
export default function Login(){ const [username, setUsername]=useState(''); const [password,setPassword]=useState(''); const nav=useNavigate();
  const submit = async (e) => { e.preventDefault(); try{ const res = await axios.post('/api/token/', {username, password}); localStorage.setItem('access', res.data.access); localStorage.setItem('refresh', res.data.refresh); nav('/dashboard'); }catch(err){ alert('Login failed') } }
  return (<Container maxWidth='xs' sx={{mt:6}}><Typography variant='h5'>Agent Login</Typography><form onSubmit={submit}><TextField fullWidth label='Username' margin='normal' value={username} onChange={e=>setUsername(e.target.value)} /><TextField fullWidth label='Password' margin='normal' type='password' value={password} onChange={e=>setPassword(e.target.value)} /><Button fullWidth variant='contained' sx={{mt:2}} type='submit'>Login</Button></form></Container>)
}
