export type Status = "PENDING" | "APPROVED" | "REJECTED";
export interface Photo { id:number; user_name:string; original_filename:string; status:Status; version:number; uploaded_at:string; reviewed_at:string|null; url:string }
export interface PhotoPage { items:Photo[]; total:number; page:number; page_size:number }
