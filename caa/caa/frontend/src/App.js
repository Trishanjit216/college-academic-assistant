import React from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import Login from './pages/Login';
import Dashboard from './pages/Dashboard';
import SeatSelector from './pages/SeatSelector';
import QRView from './pages/QRView';
import Verify from './pages/Verify';
function App(){ const token = localStorage.getItem('access'); return (<Routes><Route path='/' element={ token ? <Navigate to='/dashboard'/> : <Login/> } /><Route path='/login' element={<Login/>} /><Route path='/dashboard' element={<Dashboard/>} /><Route path='/bus/:busId/select' element={<SeatSelector/>} /><Route path='/booking/:bookingId/qr' element={<QRView/>} /><Route path='/booking/:bookingId/verify' element={<Verify/>} /></Routes>)}
export default App;
