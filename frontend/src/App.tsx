import { Route, Routes } from "react-router-dom"; import Upload from "./pages/Upload"; import Admin from "./pages/Admin"; import Tv from "./pages/Tv";
export default function App(){return <Routes><Route path="/" element={<Upload/>}/><Route path="/admin" element={<Admin/>}/><Route path="/tv" element={<Tv/>}/></Routes>}
