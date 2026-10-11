import React from 'react'; import { Link } from 'react-router-dom'; import { Container, Typography, Button } from '@mui/material';
export default function Dashboard(){ return (<Container sx={{p:3}}><Typography variant='h5'>Agent Dashboard</Typography><Button component={Link} to='/bus/1/select' variant='contained' sx={{mt:2}}>Select seats for Bus 1 (demo)</Button></Container>)}
