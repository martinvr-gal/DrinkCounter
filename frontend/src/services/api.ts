import axios from "axios"; import type { PhotoPage, Status } from "../types";
export const API_URL=import.meta.env.VITE_API_URL || "http://localhost:8000";
export const api=axios.create({baseURL:API_URL});
export const imageUrl=(path:string)=>`${API_URL}${path}`;
export const gallery=(state:string, page=1, search="")=>api.get<PhotoPage>(`/gallery/${state}`,{params:{page,page_size:50,search}}).then(x=>x.data);
export const counter=()=>api.get<{value:number}>("/api/counter").then(x=>x.data);
export const clips=()=>api.get<string[]>("/api/clips").then(x=>x.data);
export const pending=()=>api.get<PhotoPage>("/admin/pending").then(x=>x.data);
export const updateStatus=(id:number,status:Status,version:number)=>api.post(`/admin/status/${id}`,{status,version}).then(x=>x.data);
