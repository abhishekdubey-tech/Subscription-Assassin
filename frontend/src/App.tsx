import {useEffect} from 'react';
import {Routes,Route,useLocation} from 'react-router-dom';
import Landing from './pages/Landing';
import Shell from './components/Shell';
import Dashboard from './pages/Dashboard';
import Subscriptions from './pages/Subscriptions';
import Insights from './pages/Insights';
import Cancellation from './pages/Cancellation';
import Savings from './pages/Savings';
import Settings from './pages/Settings';
export default function App(){const loc=useLocation();useEffect(()=>{window.scrollTo({top:0,behavior:'instant'})},[loc.pathname]);return <Routes><Route path="/" element={<Landing/>}/><Route path="/app" element={<Shell/>}><Route index element={<Dashboard/>}/><Route path="subscriptions" element={<Subscriptions/>}/><Route path="insights" element={<Insights/>}/><Route path="cancellations" element={<Cancellation/>}/><Route path="savings" element={<Savings/>}/><Route path="settings" element={<Settings/>}/></Route></Routes>}
