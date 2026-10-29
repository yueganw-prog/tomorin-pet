using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Drawing;
using System.Drawing.Drawing2D;
using System.Drawing.Imaging;
using System.IO;
using System.IO.Compression;
using System.Media;
using Microsoft.Win32;
using System.Runtime.InteropServices;
using System.Text;
using System.Threading;
using System.Web.Script.Serialization;
using System.Windows.Forms;

namespace NaiwaDesktop
{
    internal static class Native
    {
        internal static string Title="NaiwaDesktop.Source.v1";
        internal const int Wake=0x8001, Status=0x8002;
        [StructLayout(LayoutKind.Sequential)] internal struct Point { internal int X,Y; internal Point(int x,int y){X=x;Y=y;} }
        [StructLayout(LayoutKind.Sequential)] internal struct Size { internal int W,H; internal Size(int w,int h){W=w;H=h;} }
        [StructLayout(LayoutKind.Sequential)] internal struct Rect { internal int Left,Top,Right,Bottom; }
        [StructLayout(LayoutKind.Sequential,Pack=1)] internal struct Blend { internal byte Op,Flags,Alpha,Format; }
        [StructLayout(LayoutKind.Sequential)] internal struct BitmapInfo
        {
            internal uint Size; internal int Width,Height; internal ushort Planes,BitCount;
            internal uint Compression,SizeImage; internal int XPels,YPels; internal uint Used,Important;
        }
        [DllImport("user32.dll")] internal static extern bool SetProcessDPIAware();
        [DllImport("user32.dll",CharSet=CharSet.Unicode)] internal static extern IntPtr FindWindow(string cls,string text);
        [DllImport("user32.dll")] internal static extern bool PostMessage(IntPtr h,int m,IntPtr w,IntPtr l);
        [DllImport("user32.dll")] internal static extern IntPtr SendMessage(IntPtr h,int m,IntPtr w,IntPtr l);
        [DllImport("user32.dll")] internal static extern bool IsWindowVisible(IntPtr h);
        [DllImport("user32.dll")] internal static extern bool IsIconic(IntPtr h);
        [DllImport("user32.dll")] internal static extern IntPtr GetForegroundWindow();
        [DllImport("user32.dll",CharSet=CharSet.Unicode)] internal static extern int GetClassName(IntPtr h,StringBuilder name,int count);
        [DllImport("dwmapi.dll",EntryPoint="DwmGetWindowAttribute")] internal static extern int DwmRect(IntPtr h,int attr,out Rect value,int size);
        [DllImport("dwmapi.dll",EntryPoint="DwmGetWindowAttribute")] internal static extern int DwmInt(IntPtr h,int attr,out int value,int size);
        [DllImport("user32.dll")] internal static extern bool GetWindowRect(IntPtr h,out Rect r);
        [DllImport("user32.dll")] internal static extern int GetWindowLong(IntPtr h,int index);
        [DllImport("user32.dll")] internal static extern int SetWindowLong(IntPtr h,int index,int value);
        [DllImport("user32.dll")] internal static extern bool SetForegroundWindow(IntPtr h);
        [DllImport("user32.dll")] internal static extern uint GetWindowThreadProcessId(IntPtr h,out uint id);
        [DllImport("user32.dll")] internal static extern IntPtr GetDC(IntPtr h);
        [DllImport("user32.dll")] internal static extern int ReleaseDC(IntPtr h,IntPtr dc);
        [DllImport("gdi32.dll")] internal static extern IntPtr CreateCompatibleDC(IntPtr h);
        [DllImport("gdi32.dll")] internal static extern bool DeleteDC(IntPtr h);
        [DllImport("gdi32.dll")] internal static extern bool DeleteObject(IntPtr h);
        [DllImport("gdi32.dll")] internal static extern IntPtr SelectObject(IntPtr dc,IntPtr obj);
        [DllImport("gdi32.dll")] internal static extern IntPtr CreateDIBSection(IntPtr h,ref BitmapInfo info,uint usage,out IntPtr bits,IntPtr section,uint offset);
        [DllImport("user32.dll",SetLastError=true)] internal static extern bool UpdateLayeredWindow(IntPtr h,IntPtr dest,ref Point position,ref Size size,IntPtr src,ref Point origin,uint key,ref Blend blend,uint flags);
        [DllImport("user32.dll")] internal static extern bool SetLayeredWindowAttributes(IntPtr h,uint key,byte alpha,uint flags);
        [DllImport("user32.dll")] internal static extern bool DestroyIcon(IntPtr icon);
        [DllImport("user32.dll")] internal static extern int GetGuiResources(IntPtr process,int flags);
    }

    internal static class Program
    {
        // The pet identity comes from the asset package, so several pets can coexist.
        private static void LoadTitle()
        {
            try
            {
                using(ZipArchive zip=ZipFile.OpenRead(Path.Combine(AppDomain.CurrentDomain.BaseDirectory,"素材.nwp")))
                using(StreamReader reader=new StreamReader(zip.GetEntry("metadata.json").Open()))
                {
                    object id;
                    if(new JavaScriptSerializer().Deserialize<Dictionary<string,object>>(reader.ReadToEnd()).TryGetValue("id",out id)&&!string.IsNullOrEmpty(Convert.ToString(id)))
                        Native.Title="NaiwaDesktop."+Convert.ToString(id);
                }
            }
            catch{}
        }
        [STAThread] private static void Main(string[] args)
        {
            Native.SetProcessDPIAware(); Application.EnableVisualStyles(); Application.SetCompatibleTextRenderingDefault(false); LoadTitle();
            if(args.Length>=2 && args[0]=="--self-test") { Tests.Run(args[1]); return; }
            if(args.Length>=2 && args[0]=="--demo") { Tests.Demo(args[1]); return; }
            if(args.Length>=2 && args[0]=="--probe")
            {
                IntPtr h=Native.FindWindow(null,Native.Title); Native.Rect r; Native.GetWindowRect(h,out r);
                File.WriteAllText(args[1],"Found="+(h!=IntPtr.Zero)+"\r\nVisible="+Native.IsWindowVisible(h)+"\r\nBounds="+r.Left+","+r.Top+","+r.Right+","+r.Bottom+"\r\nState="+Native.SendMessage(h,Native.Status,IntPtr.Zero,IntPtr.Zero),Encoding.UTF8); return;
            }
            if(args.Length==1 && args[0]=="--quit") { Native.PostMessage(Native.FindWindow(null,Native.Title),0x10,IntPtr.Zero,IntPtr.Zero); return; }
            bool fresh;
            using(Mutex mutex=new Mutex(true,"Local\\"+Native.Title,out fresh))
            {
                if(!fresh){Native.PostMessage(Native.FindWindow(null,Native.Title),Native.Wake,IntPtr.Zero,IntPtr.Zero);return;}
                Application.ThreadException+=delegate(object s,ThreadExceptionEventArgs e){Report(e.Exception); Application.Exit();};
                try { using(Assets assets=new Assets(AppDomain.CurrentDomain.BaseDirectory)) using(PetWindow pet=new PetWindow(assets,false)){Application.Run(pet);} }
                catch(Exception e){Report(e);}
            }
        }
        private static void Report(Exception e)
        {
            try{Directory.CreateDirectory(Settings.Folder);File.AppendAllText(Path.Combine(Settings.Folder,"error.log"),DateTime.Now.ToString("s")+" "+e+Environment.NewLine);}catch{}
            MessageBox.Show("桌宠暂时没能启动，或刚才的操作出了点问题。请确认程序与素材文件在同一文件夹。\n\n"+e.Message,"桌宠",MessageBoxButtons.OK,MessageBoxIcon.Information);
        }
    }

    internal sealed class Assets:IDisposable
    {
        internal readonly int Width,Height,Count,EyeCount,BlinkCount;
        internal readonly double Fps,Duration,BlinkFps;
        internal readonly int SingCount;
        internal readonly double SingFps;
        internal readonly string SoundFile;
        private readonly ZipArchive zip; // 素材包常驻句柄：压缩帧按需解压读取，不整体驻留内存
        private readonly Bitmap[] eyes;
        private readonly Bitmap[][] blinks;
        private readonly Dictionary<int,Bitmap> cache=new Dictionary<int,Bitmap>();
        private readonly Dictionary<int,Bitmap> singCache=new Dictionary<int,Bitmap>();
        private readonly Queue<int> order=new Queue<int>();
        private readonly Queue<int> singOrder=new Queue<int>();
        internal readonly string AudioPath;
        // 动作序列库（sing/dance/jump 通用）：按需解码 + 小 LRU 缓存
        internal sealed class Bank
        {
            internal Func<int,byte[]> Load; internal int Count; internal double Fps=30;
            internal readonly Dictionary<int,Bitmap> Cache=new Dictionary<int,Bitmap>();
            private readonly Queue<int> order=new Queue<int>();
            internal Bitmap Get(Func<byte[],Bitmap> decode,int index)
            {
                index=Math.Max(0,Math.Min(Count-1,index));Bitmap b;
                if(Cache.TryGetValue(index,out b))return b;
                b=decode(Load(index));Cache.Add(index,b);order.Enqueue(index);
                while(order.Count>14){int old=order.Dequeue();Cache[old].Dispose();Cache.Remove(old);}return b;
            }
            internal void Dispose(){foreach(Bitmap b in Cache.Values)b.Dispose();Cache.Clear();}
        }
        internal readonly Dictionary<string,Bank> Banks=new Dictionary<string,Bank>(StringComparer.OrdinalIgnoreCase);
        internal Bank Tongtou; // 通透片段复用为唱歌视觉（与 laugh 共享帧数据，零拷贝）
        internal readonly RectangleF IdleRect=new RectangleF(0.27f,0.54f,0.46f,0.46f); // 站立企鹅在画布中的占比区（气泡锚点用）
        internal readonly Dictionary<string,string> SongSeq=new Dictionary<string,string>(StringComparer.OrdinalIgnoreCase); // 歌曲文件名→动作序列
        internal string CurrentSongFile;
        // Character-specific hit/transform regions, declared by the asset package (Naiwa artwork values are the defaults).
        internal readonly string PetName,PetId;
        internal readonly double PokeX,PokeY,PokeRx,PokeRy;
        internal readonly double WarpTop,WarpBottom,WarpRx,WarpRy;
        internal readonly int IconX,IconY,IconW,IconH;
        internal int CacheCount{get{return cache.Count;}}
        private static Dictionary<string,object> Dict(Dictionary<string,object> meta,string key)
        {object v;return meta!=null&&meta.TryGetValue(key,out v)?v as Dictionary<string,object>:null;}
        private static double Num(Dictionary<string,object> meta,string key,double fallback)
        {object v;if(meta!=null&&meta.TryGetValue(key,out v)){try{return Convert.ToDouble(v);}catch{}}return fallback;}
        private static string Str(Dictionary<string,object> meta,string key,string fallback)
        {object v;string s;return meta!=null&&meta.TryGetValue(key,out v)&&!string.IsNullOrEmpty(s=Convert.ToString(v))?s:fallback;}
        private void LoadSeq(Dictionary<string,object> cfg,ZipArchive zip,string folder)
        {
            Bank b=LoadBank(cfg,zip,folder);
            if(b!=null)Banks[folder]=b;
        }
        private static Bank LoadBank(Dictionary<string,object> cfg,ZipArchive zip,string folder)
        {
            if(cfg==null)return null;
            Bank b=new Bank{Count=Convert.ToInt32(Num(cfg,"frames",0)),Fps=Num(cfg,"fps",30)};
            if(b.Count<2||b.Count>2000||b.Fps<1||b.Fps>120)throw new InvalidDataException("动作素材信息无效");
            string prefix=folder+"/";
            b.Load=delegate(int i){return Read(zip,prefix+i.ToString("0000")+".png");};
            return b;
        }
        internal Assets(string folder)
        {
            zip=ZipFile.OpenRead(Path.Combine(folder,"素材.nwp"));
            try
            {
                Dictionary<string,object> meta;
                using(StreamReader reader=new StreamReader(zip.GetEntry("metadata.json").Open())) meta=new JavaScriptSerializer().Deserialize<Dictionary<string,object>>(reader.ReadToEnd());
                Width=Convert.ToInt32(meta["width"]);Height=Convert.ToInt32(meta["height"]);Count=Convert.ToInt32(meta["frames"]);Fps=Convert.ToDouble(meta["fps"]);EyeCount=Convert.ToInt32(meta["eyeFrames"]);Duration=Count/Fps;
                if(Width<1||Height<1||Width>1024||Height>1024||Count<1||Count>2000||Fps<1||Fps>120||EyeCount<2||EyeCount>60)throw new InvalidDataException("素材信息无效");
                PetName=Str(meta,"name","奶蛙");PetId=Str(meta,"id","Source.v1");
                Dictionary<string,object> poke=Dict(meta,"poke"),warp=Dict(meta,"warp"),icon=Dict(meta,"icon");
                PokeX=Num(poke,"x",Width*.5);PokeY=Num(poke,"y",Height*.573);PokeRx=Num(poke,"rx",Width*.24);PokeRy=Num(poke,"ry",Height*.185);
                WarpTop=Num(warp,"top",Height*.285);WarpBottom=Num(warp,"bottom",Height*.815);WarpRx=Num(warp,"rx",Width*.333);WarpRy=Num(warp,"ry",Height*.196);
                IconX=Convert.ToInt32(Num(icon,"x",Width*.208));IconY=Convert.ToInt32(Num(icon,"y",Height*.109));IconW=Convert.ToInt32(Num(icon,"w",Width*.608));IconH=Convert.ToInt32(Num(icon,"h",Height*.611));
                eyes=new Bitmap[EyeCount];
                for(int i=0;i<EyeCount;i++)eyes[i]=Decode(Read(zip,"look/"+i.ToString("00")+".png"));
                BlinkCount=Convert.ToInt32(meta["blinkFrames"]);BlinkFps=Convert.ToDouble(meta["blinkFps"]);
                if(BlinkCount<2||BlinkCount>60||BlinkFps<1||BlinkFps>120)throw new InvalidDataException("眨眼素材信息无效");
                blinks=new Bitmap[2][];
                for(int mode=0;mode<2;mode++){blinks[mode]=new Bitmap[BlinkCount];for(int i=0;i<BlinkCount;i++)blinks[mode][i]=Decode(Read(zip,"blink/"+mode+"/"+i.ToString("00")+".png"));}
                object singObj;
                if(meta.TryGetValue("sing",out singObj))
                {
                    Dictionary<string,object> sing=singObj as Dictionary<string,object>;
                    if(sing!=null)
                    {
                        SingCount=Convert.ToInt32(Num(sing,"frames",0));SingFps=Num(sing,"fps",15);
                        if(SingCount<2||SingCount>2000||SingFps<1||SingFps>120)throw new InvalidDataException("唱歌素材信息无效");
                    }
                }
                SoundFile=Str(meta,"soundFile","原版笑声.wav");
                Dictionary<string,object> ir=Dict(meta,"idleRect");
                if(ir!=null)IdleRect=new RectangleF((float)Num(ir,"x",0.27),(float)Num(ir,"y",0.54),(float)Num(ir,"w",0.46),(float)Num(ir,"h",0.46));
                LoadSeq(Dict(meta,"dance"),zip,"dance");
                LoadSeq(Dict(meta,"jump"),zip,"jump");
                LoadSeq(Dict(meta,"mic"),zip,"mic");
                LoadSeq(Dict(meta,"turn"),zip,"turn");
                LoadSeq(Dict(meta,"hungry"),zip,"hungry");
                LoadSeq(Dict(meta,"closeup"),zip,"closeup");
                LoadSeq(Dict(meta,"yuai"),zip,"yuai");
                LoadSeq(Dict(meta,"qn"),zip,"qn");
                Tongtou=new Bank{Load=LaughBytes,Count=Count,Fps=Fps};
                Banks["tongtou"]=Tongtou;
                Tongtou=new Bank{Load=LaughBytes,Count=Count,Fps=Fps};
                object seqObj;
                if(meta.TryGetValue("songSeqs",out seqObj))
                {
                    Dictionary<string,object> seqs=seqObj as Dictionary<string,object>;
                    if(seqs!=null)foreach(KeyValuePair<string,object> kv in seqs){string s=Convert.ToString(kv.Value);if(!string.IsNullOrEmpty(s))SongSeq[kv.Key]=s;}
                }
            }
            catch{zip.Dispose();throw;}
            AudioPath=Path.Combine(folder,SoundFile);
            // Warm up the first frames before the first double click.
            Frame(0);Frame(1);Frame(2);
        }
        private static byte[] Read(ZipArchive zip,string name)
        { ZipArchiveEntry entry=zip.GetEntry(name);if(entry==null)throw new InvalidDataException("缺少动作素材："+name);using(Stream s=entry.Open())using(MemoryStream m=new MemoryStream()){s.CopyTo(m);return m.ToArray();} }
        private byte[] LaughBytes(int index){return Read(zip,"laugh/"+index.ToString("0000")+".png");}
        private Bitmap Decode(byte[] data)
        {
            using(MemoryStream stream=new MemoryStream(data)) using(Image image=Image.FromStream(stream))
            {
                if(image.Width!=Width||image.Height!=Height)throw new InvalidDataException("动作尺寸不一致");
                Bitmap b=new Bitmap(Width,Height,PixelFormat.Format32bppPArgb);
                using(Graphics g=Graphics.FromImage(b)){g.CompositingMode=CompositingMode.SourceCopy;g.DrawImageUnscaled(image,0,0);}return b;
            }
        }
        internal Bitmap Eye(double value){return eyes[Math.Max(0,Math.Min(EyeCount-1,(int)Math.Round(value*(EyeCount-1))))];}
        internal Bitmap Blink(double look,int frame){return blinks[look>.5?1:0][Math.Max(0,Math.Min(BlinkCount-1,frame))];}
        internal Bitmap Frame(int index)
        {
            index=Math.Max(0,Math.Min(Count-1,index));Bitmap b;
            if(cache.TryGetValue(index,out b))return b;
            b=Decode(LaughBytes(index));cache.Add(index,b);order.Enqueue(index);
            while(order.Count>12){int old=order.Dequeue();cache[old].Dispose();cache.Remove(old);}return b;
        }
        internal bool HasSing{get{return SingCount>=2;}}
        internal Bitmap SingFrame(int index)
        {
            index=Math.Max(0,Math.Min(SingCount-1,index));Bitmap b;
            if(singCache.TryGetValue(index,out b))return b;
            b=Decode(Read(zip,"sing/"+index.ToString("0000")+".png"));singCache.Add(index,b);singOrder.Enqueue(index);
            while(singOrder.Count>14){int old=singOrder.Dequeue();singCache[old].Dispose();singCache.Remove(old);}return b;
        }
        internal bool HasAction(string name)
        {
            name=SeqFor(name);
            if(name=="sing")return HasSing;
            return Banks.ContainsKey(name);
        }
        // 唱歌模式按当前歌曲解析专属序列；其余动作原样返回
        internal string SeqFor(string mode)
        {
            if(mode!="sing")return mode;
            string seq;
            return SongSeq.TryGetValue(CurrentSongFile??"",out seq)&&(seq=="sing"||HasAction(seq))?seq:"sing";
        }
        internal Bitmap ActionFrame(string name,int index)
        {
            name=SeqFor(name);
            if(name=="sing")return SingFrame(index);
            return Banks[name].Get(Decode,index);
        }
        internal double ActionFps(string name)
        {
            name=SeqFor(name);
            if(name=="sing")return SingFps;
            Bank b;return Banks.TryGetValue(name,out b)?b.Fps:30;
        }
        internal int ActionCount(string name)
        {
            name=SeqFor(name);
            if(name=="sing")return SingCount;
            Bank b;return Banks.TryGetValue(name,out b)?b.Count:0;
        }
        public void Dispose(){if(eyes!=null)foreach(Bitmap b in eyes)if(b!=null)b.Dispose();if(blinks!=null)foreach(Bitmap[] bank in blinks)foreach(Bitmap b in bank)if(b!=null)b.Dispose();foreach(Bitmap b in cache.Values)b.Dispose();cache.Clear();if(singCache!=null){foreach(Bitmap b in singCache.Values)b.Dispose();singCache.Clear();}if(zip!=null)zip.Dispose();}
    }

    internal sealed class Motion
    {
        private const double PokeDuration=.95;
        private readonly double BellyX,BellyY,BellyRx,BellyRy;
        internal double Look,Start=-1,Elapsed,Clock,BlinkStart=-1,NextBlink=4,WakeStart=-1;
        internal double PokeStart=-1,PokeX=144,PokeY=205,LandingStart=-1,DragAngle;
        internal int LandingAxis; // 0=纵向挤压（落地/撞上下），1=横向挤压（撞左右）
        internal bool Resting,Holding,Flinging;
        internal bool Playing{get{return Start>=0;}}
        internal string ActionMode; internal double ActionStart;
        internal bool Acting{get{return ActionMode!=null;}}
        internal bool Blinking{get{return BlinkStart>=0;}}
        internal bool Poking{get{return PokeStart>=0;}}
        internal bool Landing{get{return LandingStart>=0;}}
        internal bool Waking{get{return WakeStart>=0;}}
        internal bool Moving{get{return Holding||Landing||Math.Abs(DragAngle)>.02;}}
        internal Motion():this(144,211,69,68){}
        internal Motion(double bx,double by,double brx,double bry){BellyX=bx;BellyY=by;BellyRx=brx;BellyRy=bry;}
        internal double PokeAmount{get{double t=Clock-PokeStart;if(!Poking||t<0||t>=PokeDuration)return 0;return t<.12?.60*Math.Sin(t/.12*Math.PI/2):.60*Math.Exp(-4.8*(t-.12))*Math.Cos(18*(t-.12));}}
        internal double Squash{get{double t=Clock-LandingStart;return Landing&&t>=0?.055*Math.Exp(-6*t)*Math.Sin(19*t):0;}}
        internal int PlayCount;
        private double previous=-1,dragTarget,dragVelocity,lastDragTime;
        private readonly Random random=new Random();
        internal void Update(double now,bool over,double duration,double blinkDuration)
        {
            Clock=now;double dt=previous<0?0:Math.Min(.05,Math.Max(0,now-previous));previous=now;
            double goal=over?1:0,step=dt/.18;Look+=Math.Max(-step,Math.Min(step,goal-Look));
            if(Playing){Elapsed=Math.Max(0,now-Start);if(Elapsed>=duration){Start=-1;Elapsed=duration;Resting=true;}}
            if(Waking&&now-WakeStart>=.24)WakeStart=-1;
            if(Poking&&now-PokeStart>=PokeDuration)PokeStart=-1;
            if(Landing&&now-LandingStart>=.9)LandingStart=-1;
            if(Blinking&&now-BlinkStart>=blinkDuration){BlinkStart=-1;ScheduleBlink(now);}
            if(!Playing&&!Acting&&!Resting&&!Holding&&!Landing&&!Poking&&!Waking&&!Blinking&&!Flinging&&now>=NextBlink)BlinkStart=now;
            if(!Flinging)
            {
                if(!Holding||now-lastDragTime>.10)dragTarget=0;
                // Critically damped tilt; bounded steps keep long timer gaps stable.
                int steps=Math.Max(1,(int)Math.Ceiling(dt/.008));double stepTime=dt/steps;
                for(int i=0;i<steps;i++){dragVelocity+=(160*(dragTarget-DragAngle)-25*dragVelocity)*stepTime;DragAngle+=dragVelocity*stepTime;}
                DragAngle=Math.Max(-7,Math.Min(7,DragAngle));
                if(!Holding&&Math.Abs(DragAngle)<.02&&Math.Abs(dragVelocity)<.05){DragAngle=0;dragVelocity=0;}
            }
        }
        private void ScheduleBlink(double now){NextBlink=now+4+random.NextDouble()*4;}
        private void ClearEffects(double now){Clock=now;BlinkStart=PokeStart=WakeStart=LandingStart=-1;ActionMode=null;Flinging=false;Holding=false;DragAngle=dragTarget=dragVelocity=0;ScheduleBlink(now);}
        internal bool Laugh(double now){if(Playing)return false;ClearEffects(now);Resting=false;Start=now;Elapsed=0;PlayCount++;return true;}
        internal void Stop(){Start=-1;Elapsed=0;Resting=false;ClearEffects(Clock);}
        internal void StartAction(string name,double now){if(Acting&&ActionMode==name)return;ClearEffects(now);Resting=false;ActionMode=name;ActionStart=now;}
        internal void StopAction(){if(!Acting)return;ActionMode=null;ClearEffects(Clock);}
        internal void LaunchFling(double now){ClearEffects(now);Resting=false;Flinging=true;}
        internal void EndFling(double now){if(!Flinging)return;Flinging=false;LandingStart=now;LandingAxis=0;ScheduleBlink(now);}
        internal void Stand(double now){if(!Resting)return;Resting=false;ClearEffects(now);WakeStart=now;}
        internal bool InBelly(double x,double y){double dx=(x-BellyX)/BellyRx,dy=(y-BellyY)/BellyRy;return dx*dx+dy*dy<=1;}
        internal bool Poke(double now,double x,double y){if(Playing||Acting||Resting||Holding||Flinging||!InBelly(x,y))return false;ClearEffects(now);PokeStart=now;PokeX=x;PokeY=y;return true;}
        internal void BeginDrag(double now){string act=ActionMode;Start=-1;Elapsed=0;ClearEffects(now);ActionMode=act;Holding=true;lastDragTime=now;} // 拖拽不打断进行中的动作
        internal void Drag(double now,double dx){if(!Holding)BeginDrag(now);double dt=Math.Max(1.0/120,now-lastDragTime);lastDragTime=now;dragTarget=Math.Max(-7,Math.Min(7,dx/dt*.013));Clock=now;}
        internal void EndDrag(double now){if(!Holding)return;Holding=false;dragTarget=0;Clock=now;LandingStart=now;ScheduleBlink(now);}
        internal void Suspend(double now){Start=-1;Elapsed=0;Look=0;ClearEffects(now);}
        internal void Bounce(int axis,double now){LandingStart=now;LandingAxis=axis;}
    }

    internal static class Fullscreen
    {
        internal static bool Covers(Rectangle window,Rectangle screen,int style,string name)
        {
            if((style&0x00c00000)!=0||name=="Progman"||name=="WorkerW"||name=="Shell_TrayWnd"||name=="Shell_SecondaryTrayWnd")return false;
            const int tolerance=2;
            return window.Left<=screen.Left+tolerance&&window.Top<=screen.Top+tolerance&&window.Right>=screen.Right-tolerance&&window.Bottom>=screen.Bottom-tolerance;
        }
        internal static bool IsActive(IntPtr window,IntPtr pet,Rectangle screen)
        {
            if(window==IntPtr.Zero||window==pet||!Native.IsWindowVisible(window)||Native.IsIconic(window))return false;
            Native.Rect r;if(!Native.GetWindowRect(window,out r))return false;
            try{int cloaked;if(Native.DwmInt(window,14,out cloaked,4)==0&&cloaked!=0)return false;Native.Rect frame;if(Native.DwmRect(window,9,out frame,16)==0)r=frame;}catch(DllNotFoundException){}catch(EntryPointNotFoundException){}
            StringBuilder cls=new StringBuilder(256);Native.GetClassName(window,cls,cls.Capacity);
            return Covers(Rectangle.FromLTRB(r.Left,r.Top,r.Right,r.Bottom),screen,Native.GetWindowLong(window,-16),cls.ToString());
        }
    }

    internal sealed class FullscreenGate
    {
        internal bool Hidden;
        private bool candidate;
        private double since;
        internal bool Update(bool detected,double now)
        {
            if(candidate!=detected){candidate=detected;since=now;}
            if(candidate!=Hidden&&now-since>=(candidate?.15:.25)){Hidden=candidate;return true;}return false;
        }
        internal void Reset(){Hidden=candidate=false;since=0;}
        internal void Set(bool value,double now){Hidden=candidate=value;since=now;}
    }

    internal sealed class Gesture
    {
        private const double LaunchMin=150,TrendMin=30,DispMin=80; // naiwa-pet 物理甩出阈值
        internal bool Pressed,Dragged;
        internal Point Origin;
        private Point lastClickPoint;
        private double lastClick=-100;
        private readonly List<double[]> history=new List<double[]>(); // x,y,t(s)
        internal void Down(Point p){Pressed=true;Dragged=false;Origin=p;history.Clear();history.Add(new double[]{p.X,p.Y,0});}
        internal void Move(Point p,double now){if(!Pressed)return;history.Add(new[]{p.X,p.Y,now});if(history.Count>40)history.RemoveAt(0);if(Math.Abs(p.X-Origin.X)>5||Math.Abs(p.Y-Origin.Y)>5)Dragged=true;}
        // 甩出判定：总位移足够 + 末段(0~100ms)明显快于前段(100~200ms) + 末段速度够大
        internal bool TryLaunch(out double vx,out double vy)
        {
            vx=vy=0;if(history.Count<2)return false;
            double[] press=history[0],last=history[history.Count-1];
            double disp=Math.Sqrt(Math.Pow(last[0]-press[0],2)+Math.Pow(last[1]-press[1],2));
            if(disp<DispMin)return false;
            double refT=last[2],ef=-1,el=-1,lf=-1,ll=-1;double[] ep=null,ep2=null,lp=null,lp2=null;
            foreach(double[] h in history)
            {
                double age=refT-h[2];
                if(age>.10&&age<=.20){if(ef<0){ef=h[2];ep=h;}el=h[2];ep2=h;}
                else if(age>=0&&age<=.10){if(lf<0){lf=h[2];lp=h;}ll=h[2];lp2=h;}
            }
            double[] vLate=AvgVel(lp,lp2,lf,ll),vEarly=AvgVel(ep,ep2,ef,el);
            double speedLate=Math.Sqrt(vLate[0]*vLate[0]+vLate[1]*vLate[1]);
            double trend=speedLate-Math.Sqrt(vEarly[0]*vEarly[0]+vEarly[1]*vEarly[1]);
            if(trend>TrendMin&&speedLate>LaunchMin){vx=vLate[0];vy=vLate[1];history.Clear();return true;}
            return false;
        }
        private static double[] AvgVel(double[] a,double[] b,double ta,double tb)
        {
            if(a==null||b==null||tb-ta<=.001)return new double[]{0,0};
            return new double[]{(b[0]-a[0])/(tb-ta),(b[1]-a[1])/(tb-ta)};
        }
        internal bool Up(Point p,double now)
        {
            if(!Pressed)return false;Pressed=false;
            if(Dragged){lastClick=-100;return false;}
            bool twice=now-lastClick<=SystemInformation.DoubleClickTime/1000.0&&Math.Abs(p.X-lastClickPoint.X)<=SystemInformation.DoubleClickSize.Width&&Math.Abs(p.Y-lastClickPoint.Y)<=SystemInformation.DoubleClickSize.Height;
            lastClick=twice?-100:now;lastClickPoint=p;return twice;
        }
        internal void Cancel(){Pressed=false;Dragged=false;lastClick=-100;history.Clear();}
    }

    internal sealed class Settings
    {
        internal int Scale=85,X,Y;internal bool Position,Sound=true,OnTop=true,AutoHide=true,RandomTalk=true;
        internal double Minutes;
        internal static string Folder{get{return Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),"NaiwaDesktopPet");}}
        // Each pet keeps its own settings so several pets do not overwrite each other.
        internal static string FolderFor(string id){return Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),"NaiwaDesktopPet-"+(string.IsNullOrEmpty(id)?"Source.v1":id));}
        internal static Settings Load(string id)
        {
            Settings s=new Settings();try{
                string file=Path.Combine(FolderFor(id),"settings.ini");if(!File.Exists(file))return s;
                foreach(string line in File.ReadAllLines(file)){string[] p=line.Split('=');int n;double d;if(p.Length!=2)continue;
                    if(p[0]=="scale"&&int.TryParse(p[1],out n))s.Scale=Math.Max(50,Math.Min(150,n));
                    if(p[0]=="x"&&int.TryParse(p[1],out n)){s.X=n;s.Position=true;}
                    if(p[0]=="y"&&int.TryParse(p[1],out n))s.Y=n;
                    if(p[0]=="sound")s.Sound=p[1]=="True";
                    if(p[0]=="top")s.OnTop=p[1]!="False";
                    if(p[0]=="fullscreen")s.AutoHide=p[1]!="False";
                    if(p[0]=="randomtalk")s.RandomTalk=p[1]!="False";
                    if(p[0]=="minutes"&&double.TryParse(p[1],System.Globalization.NumberStyles.Float,System.Globalization.CultureInfo.InvariantCulture,out d))s.Minutes=d;
                }
            }catch{}return s;
        }
        internal void Save(string id){try{Directory.CreateDirectory(FolderFor(id));File.WriteAllLines(Path.Combine(FolderFor(id),"settings.ini"),new string[]{"scale="+Scale,"x="+X,"y="+Y,"sound="+Sound,"top="+OnTop,"fullscreen="+AutoHide,"randomtalk="+RandomTalk,"minutes="+Minutes.ToString("0.##",System.Globalization.CultureInfo.InvariantCulture)});}catch{}}
    }

    internal sealed class LayeredSurface:IDisposable
    {
        private IntPtr dc,bmp,old,bits;
        private byte[] buffer;
        private int width,height;
        internal void Update(IntPtr window,Bitmap image,Point location)
        {
            if(width!=image.Width||height!=image.Height)Create(image.Width,image.Height);
            BitmapData locked=image.LockBits(new Rectangle(0,0,width,height),ImageLockMode.ReadOnly,PixelFormat.Format32bppPArgb);
            try{Marshal.Copy(locked.Scan0,buffer,0,buffer.Length);Marshal.Copy(buffer,0,bits,buffer.Length);}finally{image.UnlockBits(locked);}
            Native.Point destination=new Native.Point(location.X,location.Y),origin=new Native.Point(0,0);Native.Size size=new Native.Size(width,height);
            Native.Blend blend=new Native.Blend{Op=0,Flags=0,Alpha=255,Format=1};
            if(!Native.UpdateLayeredWindow(window,IntPtr.Zero,ref destination,ref size,dc,ref origin,0,ref blend,2))throw new System.ComponentModel.Win32Exception(Marshal.GetLastWin32Error());
        }
        private void Create(int w,int h)
        {
            Dispose();width=w;height=h;buffer=new byte[w*h*4];dc=Native.CreateCompatibleDC(IntPtr.Zero);
            Native.BitmapInfo info=new Native.BitmapInfo{Size=40,Width=w,Height=-h,Planes=1,BitCount=32,Compression=0,SizeImage=(uint)(w*h*4)};
            bmp=Native.CreateDIBSection(dc,ref info,0,out bits,IntPtr.Zero,0);
            if(bmp==IntPtr.Zero)throw new InvalidOperationException("无法创建透明窗口");old=Native.SelectObject(dc,bmp);
        }
        internal bool Hit(int x,int y){return buffer!=null&&x>=0&&y>=0&&x<width&&y<height&&buffer[(y*width+x)*4+3]>24;}
        public void Dispose(){if(dc!=IntPtr.Zero){if(old!=IntPtr.Zero)Native.SelectObject(dc,old);if(bmp!=IntPtr.Zero)Native.DeleteObject(bmp);Native.DeleteDC(dc);}dc=bmp=old=bits=IntPtr.Zero;width=height=0;buffer=null;}
    }

    internal static class Renderer
    {
        internal static Icon CreateIcon(Assets assets)
        {
            Rectangle face=new Rectangle(assets.IconX,assets.IconY,assets.IconW,assets.IconH);
            using(Bitmap small=new Bitmap(64,64,PixelFormat.Format32bppArgb))
            {
                using(Graphics g=Graphics.FromImage(small)){g.InterpolationMode=InterpolationMode.HighQualityBicubic;g.DrawImage(assets.Eye(0),new Rectangle(6,0,52,64),face,GraphicsUnit.Pixel);}
                IntPtr h=small.GetHicon();try{using(Icon borrowed=Icon.FromHandle(h))return (Icon)borrowed.Clone();}finally{Native.DestroyIcon(h);}
            }
        }
        internal static Bitmap Render(Assets assets,Motion m,int scale)
        {
            int w=assets.Width*scale/100,h=assets.Height*scale/100;
            Bitmap canvas=new Bitmap(w,h,PixelFormat.Format32bppPArgb);
            using(Graphics g=Graphics.FromImage(canvas))
            {
                g.Clear(Color.Transparent);g.InterpolationMode=InterpolationMode.HighQualityBicubic;g.PixelOffsetMode=PixelOffsetMode.HighQuality;
                // Transforms move the supplied artwork; no replacement body or expression is drawn.
                if(m.Moving)
                {
                    float px=w*.5f,py=h*(m.Holding?.56f:.9565f),s=(float)m.Squash;
                    g.TranslateTransform(px,py-(m.Holding?2f*scale/100:0));g.RotateTransform((float)m.DragAngle);
                    float sx,sy;
                    if(m.Holding){sx=1.008f;sy=1.018f;}
                    else if(m.LandingAxis==1){sx=1-s;sy=1+s;}
                    else{sx=1+s;sy=1-s;}
                    g.ScaleTransform(sx,sy);g.TranslateTransform(-px,-py);
                }
                Rectangle rect=new Rectangle(0,0,w,h);
                if(m.Resting)Draw(g,assets.Frame(assets.Count-1),rect,1);
                else if(m.Waking){float t=(float)Math.Min(1,(m.Clock-m.WakeStart)/.24);Draw(g,assets.Frame(assets.Count-1),rect,1-t);Draw(g,assets.Eye(m.Look),rect,t);}
                else if(m.Acting)Draw(g,assets.ActionFrame(m.ActionMode,(int)((m.Clock-m.ActionStart)*assets.ActionFps(m.ActionMode))%assets.ActionCount(m.ActionMode)),rect,1);
                else if(!m.Playing)
                {
                    // Idle micro-life: float bob + gentle bottom-anchored breathing.
                    bool idleLife=!m.Moving&&!m.Flinging;
                    float bob=idleLife?(float)(6*Math.Sin(m.Clock*2*Math.PI/2.36)):0f;
                    float br=idleLife?1f+0.006f*(float)Math.Sin(m.Clock*2*Math.PI/3.2):1f;
                    g.TranslateTransform(0,bob);
                    g.TranslateTransform(w*.5f,h*.98f);g.ScaleTransform(1f,br);g.TranslateTransform(-w*.5f,-h*.98f);
                    Bitmap idle=m.Blinking?assets.Blink(m.Look,(int)((m.Clock-m.BlinkStart)*assets.BlinkFps)):assets.Eye(m.Look);
                    if(m.Poking)using(Bitmap poke=WarpBelly(assets,idle,m.PokeX,m.PokeY,m.PokeAmount))Draw(g,poke,rect,1);else Draw(g,idle,rect,1);
                    g.TranslateTransform(w*.5f,h*.98f);g.ScaleTransform(1f,1f/br);g.TranslateTransform(-w*.5f,-h*.98f);
                    g.TranslateTransform(0,-bob);
                }
                else if(m.Elapsed<.10){Draw(g,assets.Eye(m.Look),rect,1);Draw(g,assets.Frame((int)(m.Elapsed*assets.Fps)),rect,(float)(m.Elapsed/.10));}
                else Draw(g,assets.Frame((int)(m.Elapsed*assets.Fps)),rect,1);
            }return canvas;
        }
        internal static Bitmap WarpBelly(Assets assets,Bitmap original,double cx,double cy,double amount)
        {
            int w=original.Width,h=original.Height;byte[] source=new byte[w*h*4];
            BitmapData locked=original.LockBits(new Rectangle(0,0,w,h),ImageLockMode.ReadOnly,PixelFormat.Format32bppPArgb);
            try{Marshal.Copy(locked.Scan0,source,0,source.Length);}finally{original.UnlockBits(locked);}
            byte[] result=(byte[])source.Clone();
            double radiusX=assets.WarpRx,radiusY=assets.WarpRy,neckY=assets.WarpTop,legY=assets.WarpBottom;
            int left=Math.Max(0,(int)(cx-radiusX)),right=Math.Min(w-2,(int)(cx+radiusX)),top=Math.Max((int)neckY,(int)(cy-radiusY)),bottom=Math.Min(Math.Min((int)legY,h-2),(int)(cy+radiusY));
            for(int y=top;y<=bottom;y++)for(int x=left;x<=right;x++)
            {
                double dx=x-cx,dy=y-cy,r=dx*dx/(radiusX*radiusX)+dy*dy/(radiusY*radiusY);if(r>=1)continue;
                // Include the belly outline, fading out before the face and feet.
                double neck=Math.Min(1,(y-neckY)/30.0),legs=Math.Min(1,(legY-y)/20.0);
                double fade=neck*neck*(3-2*neck)*legs*legs*(3-2*legs);
                double fall=(1-r)*(1-r)*amount*fade;
                double sx=Math.Max(0,Math.Min(w-1.001,x+dx*fall)),sy=Math.Max(0,Math.Min(h-1.001,y+dy*fall*.6));
                int ix=Math.Max(0,Math.Min(w-2,(int)sx)),iy=Math.Max(0,Math.Min(h-2,(int)sy));double fx=sx-ix,fy=sy-iy;
                int dest=(y*w+x)*4,a=(iy*w+ix)*4,b=a+4,c=a+w*4,d=c+4;
                for(int channel=0;channel<4;channel++)result[dest+channel]=(byte)Math.Max(0,Math.Min(255,(source[a+channel]*(1-fx)+source[b+channel]*fx)*(1-fy)+(source[c+channel]*(1-fx)+source[d+channel]*fx)*fy));
            }
            Bitmap warped=new Bitmap(w,h,PixelFormat.Format32bppPArgb);locked=warped.LockBits(new Rectangle(0,0,w,h),ImageLockMode.WriteOnly,PixelFormat.Format32bppPArgb);
            try{Marshal.Copy(result,0,locked.Scan0,result.Length);}finally{warped.UnlockBits(locked);}return warped;
        }
        private static void Draw(Graphics g,Bitmap b,Rectangle rect,float alpha)
        {
            if(alpha<=0)return;
            using(ImageAttributes a=new ImageAttributes())
            {
                a.SetWrapMode(WrapMode.TileFlipXY);if(alpha<1){ColorMatrix c=new ColorMatrix();c.Matrix33=alpha;a.SetColorMatrix(c);}
                g.DrawImage(b,rect,0,0,b.Width,b.Height,GraphicsUnit.Pixel,a);
            }
        }
    }

    // ============================================================
    // Physics —— 物理甩飞（移植 naiwa-pet pet.py：重力/空气阻力/边缘反弹）
    // pet.py 用 px/帧@60fps；这里换算成 px/s：0.32px/帧²→1152px/s²，0.98^帧→e^(-1.212t)
    // ============================================================
    internal sealed class Physics
    {
        private const double Gravity=1152,BounceK=.70,StopSpeed=30,MinBounce=180;
        internal bool Active;
        private double vx,vy;
        internal double Vx{get{return vx;}}
        internal void Launch(double ivx,double ivy){vx=ivx;vy=ivy;Active=true;}
        internal void Stop(){Active=false;vx=vy=0;}
        internal void Update(Motion m,double now,double dt,Point location,Size size,Rectangle area,out Point next)
        {
            vy+=Gravity*dt;double k=Math.Exp(-1.212*dt);vx*=k;vy*=k;
            int x=location.X+(int)Math.Round(vx*dt),y=location.Y+(int)Math.Round(vy*dt);
            if(x<area.Left){x=area.Left;if(Math.Abs(vx)>=MinBounce){vx=Math.Abs(vx)*BounceK;m.Bounce(1,now);}else vx=0;}
            else if(x>area.Right-size.Width){x=area.Right-size.Width;if(Math.Abs(vx)>=MinBounce){vx=-Math.Abs(vx)*BounceK;m.Bounce(1,now);}else vx=0;}
            if(y<area.Top){y=area.Top;if(Math.Abs(vy)>=MinBounce){vy=Math.Abs(vy)*BounceK;m.Bounce(0,now);}else vy=0;}
            else if(y>area.Bottom-size.Height){y=area.Bottom-size.Height;if(Math.Abs(vy)>=MinBounce){vy=-Math.Abs(vy)*BounceK;m.Bounce(0,now);}else vy=0;}
            next=new Point(x,y);
            if(Speed<StopSpeed)Stop();
        }
        private double Speed{get{return Math.Sqrt(vx*vx+vy*vy);}}
    }

    // ============================================================
    // MusicPlayer —— WPF MediaPlayer 包装（独立 STA 线程，直接播 m4a/mp3/wav）
    // ============================================================
    internal sealed class MusicPlayer:IDisposable
    {
        private Thread thread;
        private System.Windows.Threading.Dispatcher dispatcher;
        private System.Windows.Media.MediaPlayer player;
        internal readonly List<string> Songs=new List<string>();
        internal int Index;
        internal bool IsPlaying,IsPaused;
        internal event Action SongEnded;
        internal event Action SongChanged; // 每次切歌触发（调用方线程）
        internal bool HasSongs{get{return Songs.Count>0;}}
        internal string CurrentSong{get{return HasSongs?Songs[Math.Max(0,Math.Min(Songs.Count-1,Index))]:null;}}
        internal void Start()
        {
            using(var ready=new System.Threading.ManualResetEvent(false))
            {
                thread=new Thread(delegate()
                {
                    player=new System.Windows.Media.MediaPlayer{Volume=.9};
                    player.MediaEnded+=delegate{IsPlaying=false;if(SongEnded!=null)SongEnded();};
                    dispatcher=System.Windows.Threading.Dispatcher.CurrentDispatcher;
                    ready.Set();
                    System.Windows.Threading.Dispatcher.Run();
                });
                thread.SetApartmentState(ApartmentState.STA);thread.IsBackground=true;thread.Start();
                ready.WaitOne();
            }
        }
        private void Post(Action action){if(dispatcher==null)return;dispatcher.BeginInvoke(action);}
        internal void LoadSongs(string folder)
        {
            Songs.Clear();
            try{if(Directory.Exists(folder))foreach(string f in Directory.GetFiles(folder))if(Array.IndexOf(new[]{".mp3",".m4a",".wav",".flac",".ogg"},Path.GetExtension(f).ToLower())>=0)Songs.Add(f);}catch{}
            Songs.Sort(StringComparer.OrdinalIgnoreCase);
        }
        internal void Play(int index)
        {
            if(!HasSongs)return;
            if(dispatcher==null)Start(); // 懒启动：首次播放才拉起 STA 播放线程
            Index=((index%Songs.Count)+Songs.Count)%Songs.Count;
            string file=Songs[Index];Post(delegate{try{player.Open(new Uri(file));player.Play();IsPlaying=true;IsPaused=false;}catch{}});
            if(SongChanged!=null)SongChanged();
        }
        internal void TogglePause(){Post(delegate{try{if(IsPaused){player.Play();IsPaused=false;}else if(IsPlaying){player.Pause();IsPaused=true;}}catch{}});}
        internal void StopPlay(){Post(delegate{try{player.Stop();IsPlaying=false;IsPaused=false;}catch{}});}
        public void Dispose(){try{if(dispatcher!=null)Post(delegate{dispatcher.InvokeShutdown();});}catch{}}
    }

    // ============================================================
    // SingBar —— 唱歌控制栏（不抢焦点的小工具条）
    // ============================================================
    internal sealed class SingBar:Form
    {
        internal event Action TogglePause,PrevSong,NextSong,StopSing;
        internal event Action<bool> BarClosed;
        internal readonly Button toggleButton=new Button();
        internal readonly Label songLabel=new Label();
        internal SingBar()
        {
            FormBorderStyle=FormBorderStyle.None;ShowInTaskbar=false;StartPosition=FormStartPosition.Manual;
            TopMost=true;
            BackColor=Color.FromArgb(24,24,30);
            ControlBox=false;MaximizeBox=false;MinimizeBox=false;DoubleBuffered=true;
            Font=new Font("Segoe UI Symbol",11f);
            Button prev=new Button{Text="⏮",FlatStyle=FlatStyle.Flat,Size=new Size(40,34),Location=new Point(4,3),TabIndex=0};
            toggleButton.Text="⏸";toggleButton.FlatStyle=FlatStyle.Flat;toggleButton.Size=new Size(40,34);toggleButton.Location=new Point(46,3);toggleButton.TabIndex=1;
            Button next=new Button{Text="⏭",FlatStyle=FlatStyle.Flat,Size=new Size(40,34),Location=new Point(88,3),TabIndex=2};
            Button stop=new Button{Text="✕",FlatStyle=FlatStyle.Flat,Size=new Size(34,34),Location=new Point(130,3),TabIndex=3};
            songLabel.Text="";songLabel.AutoSize=false;songLabel.Size=new Size(150,34);songLabel.Location=new Point(166,3);songLabel.TextAlign=ContentAlignment.MiddleLeft;songLabel.ForeColor=Color.Gainsboro;
            foreach(Button b in new[]{prev,toggleButton,next,stop}){b.BackColor=Color.FromArgb(38,38,48);b.ForeColor=Color.Gainsboro;b.FlatAppearance.BorderColor=Color.FromArgb(70,70,84);}
            prev.Click+=delegate{if(PrevSong!=null)PrevSong();};
            toggleButton.Click+=delegate{if(TogglePause!=null)TogglePause();};
            next.Click+=delegate{if(NextSong!=null)NextSong();};
            stop.Click+=delegate{if(StopSing!=null)StopSing();};
            Controls.AddRange(new Control[]{prev,toggleButton,next,stop,songLabel});
            ClientSize=new Size(318,40);
            FormClosing+=delegate{if(BarClosed!=null)BarClosed(false);};
        }
        protected override bool ShowWithoutActivation{get{return true;}}
        protected override CreateParams CreateParams{get{CreateParams p=base.CreateParams;p.ExStyle|=0x80000|0x80|0x08000000;return p;}}
        // 手动加了 WS_EX_LAYERED 就必须补分层属性，否则窗口内容永远不可见
        protected override void OnHandleCreated(EventArgs e){base.OnHandleCreated(e);Native.SetLayeredWindowAttributes(Handle,0,255,2);}
        internal void UpdateState(string song,bool paused){toggleButton.Text=paused?"▶":"⏸";songLabel.Text=song;}
    }

    // ============================================================
    // GreetingBubble —— 问候气泡（陪伴时长）
    // ============================================================
    internal sealed class GreetingBubble:Form
    {
        private readonly System.Windows.Forms.Timer life=new System.Windows.Forms.Timer();
        internal GreetingBubble(string text,Rectangle pet,int seconds=9)
        {
            FormBorderStyle=FormBorderStyle.None;ShowInTaskbar=false;StartPosition=FormStartPosition.Manual;
            TopMost=true;
            BackColor=Color.FromArgb(246,248,252);
            Label label=new Label{Text=text,Font=new Font("Microsoft YaHei UI",10f),ForeColor=Color.FromArgb(50,54,66),TextAlign=ContentAlignment.MiddleLeft,Padding=new Padding(12,8,12,8)};
            const int maxW=240;
            // 测量与渲染同源：用 Label 自身的 GetPreferredSize（含 Padding、真实断行），杜绝算短截字
            Size pref=label.GetPreferredSize(new Size(maxW,0));
            ClientSize=new Size(Math.Min(maxW,pref.Width)+8,pref.Height+8);
            label.Dock=DockStyle.Fill;
            Controls.Add(label);
            Region=new Region(RoundedPath(ClientSize,10));
            life.Interval=seconds*1000;life.Tick+=delegate{Close();};life.Start();
            // 贴身摆放：右侧齐头 → 塞不下换左侧 → 再贴头顶
            Rectangle area=Screen.FromPoint(pet.Location).WorkingArea;
            int x=pet.Right+6,y=pet.Top-6;
            if(x+Width>area.Right-4)
            {
                x=pet.Left-Width-6;
                if(x<area.Left+4){x=Math.Max(area.Left+4,Math.Min(pet.Left+pet.Width/2-Width/2,area.Right-Width-4));y=pet.Top-Height-10;}
            }
            y=Math.Max(area.Top+4,Math.Min(y,area.Bottom-Height-4));
            Location=new Point(x,y);
        }
        internal static System.Drawing.Drawing2D.GraphicsPath RoundedPath(Size size,int radius)
        {
            System.Drawing.Drawing2D.GraphicsPath path=new System.Drawing.Drawing2D.GraphicsPath();
            path.AddArc(0,0,radius,radius,180,90);path.AddArc(size.Width-radius,0,radius,radius,270,90);
            path.AddArc(size.Width-radius,size.Height-radius,radius,radius,0,90);path.AddArc(0,size.Height-radius,radius,radius,90,90);
            path.CloseFigure();return path;
        }
        protected override bool ShowWithoutActivation{get{return true;}}
        protected override CreateParams CreateParams{get{CreateParams p=base.CreateParams;p.ExStyle|=0x80000|0x80|0x08000000;return p;}}
        protected override void OnHandleCreated(EventArgs e){base.OnHandleCreated(e);Native.SetLayeredWindowAttributes(Handle,0,255,2);}
        protected override void OnPaintBackground(PaintEventArgs e){base.OnPaintBackground(e);}
        protected override void Dispose(bool disposing){if(disposing){life.Dispose();}base.Dispose(disposing);}
    }

    internal sealed class PetWindow:Form
    {
        private readonly Assets assets;
        private readonly bool testing;
        private readonly Settings settings;
        internal readonly Motion Motion;
        private readonly Gesture gesture=new Gesture();
        private readonly Stopwatch watch=Stopwatch.StartNew();
        private readonly System.Windows.Forms.Timer timer=new System.Windows.Forms.Timer();
        private readonly LayeredSurface surface=new LayeredSurface();
        private readonly SoundPlayer sound;
        private readonly Icon petIcon;
        private readonly ContextMenuStrip menu;
        private readonly NotifyIcon tray;
    private ToolStripMenuItem soundItem,topItem,stopItem,fullscreenItem,singItem,randomItem,autostartItem;
    private readonly SoundPlayer danceSound,jumpSound,hungrySound;
    private readonly Random rng=new Random();
    private double lastPop;
    private Point dragWindow,lastDragPointer;
    private readonly FullscreenGate fullscreenGate=new FullscreenGate();
    private double nextFullscreenCheck,lastTickNow,minuteMark,lastMinutesSave;
    private readonly Physics physics=new Physics();
    private readonly MusicPlayer music=new MusicPlayer();
    private readonly SingBar singBar=new SingBar();
    private string lastVisual="";
        private bool disposing,menuOpen,ready;
        internal bool HiddenForFullscreen{get;private set;}
        internal int ScalePercent{get{return settings.Scale;}}
        internal bool SoundEnabled{get{return settings.Sound;}}
        private double Now{get{return watch.Elapsed.TotalSeconds;}}

        internal PetWindow(Assets a,bool test)
        {
            assets=a;testing=test;settings=testing?new Settings():Settings.Load(assets.PetId);
            Motion=new Motion(a.PokeX,a.PokeY,a.PokeRx,a.PokeRy);
            Text=Native.Title;FormBorderStyle=FormBorderStyle.None;ShowInTaskbar=false;StartPosition=FormStartPosition.Manual;AutoScaleMode=AutoScaleMode.None;
            SetStyle(ControlStyles.UserPaint|ControlStyles.AllPaintingInWmPaint|ControlStyles.StandardClick|ControlStyles.StandardDoubleClick,true);
            ClientSize=SizeFor(settings.Scale);TopMost=settings.OnTop;Cursor=Cursors.Hand;
            if(settings.Position)Location=new Point(settings.X,settings.Y);else Home();
            KeepVisible();
            petIcon=Renderer.CreateIcon(assets);
            Icon=petIcon;
            if(File.Exists(assets.AudioPath)){sound=new SoundPlayer(assets.AudioPath);sound.Load();}
            menu=BuildMenu();
            if(!testing){tray=new NotifyIcon{Icon=petIcon,Text=assets.PetName+" · 戳肚子 / 双击笑 / 拖动",ContextMenuStrip=menu,Visible=true};tray.DoubleClick+=delegate{ReturnHome();};}
            music.LoadSongs(Path.Combine(AppDomain.CurrentDomain.BaseDirectory,"music"));
            music.SongEnded+=delegate{PlayNextSong();};
            music.SongChanged+=delegate{assets.CurrentSongFile=Path.GetFileName(music.CurrentSong??"");if(singBar.Visible)UpdateBar();};
            Func<string,SoundPlayer> side=delegate(string file)
            {
                string p=Path.Combine(AppDomain.CurrentDomain.BaseDirectory,file);
                if(!File.Exists(p))return null;
                SoundPlayer sp=new SoundPlayer(p);sp.Load();return sp;
            };
            danceSound=side("dance.wav");jumpSound=side("jump.wav");hungrySound=side("hungry.wav");
            if(!testing){EnsureLines();lastPop=Now;}
            singBar.TogglePause+=delegate{music.TogglePause();UpdateBar();};
            singBar.PrevSong+=delegate{music.Play(music.Index-1);UpdateBar();};
            singBar.NextSong+=delegate{music.Play(music.Index+1);UpdateBar();};
            singBar.StopSing+=delegate{StopAction();};
            timer.Interval=16;timer.Tick+=delegate{Tick();};
            Shown+=delegate{ready=true;RenderNow(true);if(!testing){CheckFullscreen(true);timer.Start();ShowGreeting();}};
        }
        protected override bool ShowWithoutActivation{get{return true;}}
        protected override CreateParams CreateParams{get{CreateParams p=base.CreateParams;p.ExStyle|=0x80000|0x80|0x08000000;p.ClassStyle|=8;return p;}}
        protected override void WndProc(ref Message m)
        {
            if(m.Msg==Native.Wake){ReturnHome();return;}
            if(m.Msg==Native.Status){m.Result=(IntPtr)(HiddenForFullscreen?4:Motion.Resting?3:Motion.Playing?2:Motion.Look>.5?1:0);return;}
            if(m.Msg==0x21){m.Result=(IntPtr)3;return;}
            if(m.Msg==0x84 && ready && !gesture.Pressed)
            {
                long value=m.LParam.ToInt64();Point p=PointToClient(new Point((short)(value&0xffff),(short)((value>>16)&0xffff)));
                m.Result=surface.Hit(p.X,p.Y)?(IntPtr)1:new IntPtr(-1);return;
            }
            base.WndProc(ref m);
            if(m.Msg==0x7e && ready){KeepVisible();RenderNow(true);Save();}
        }
        private ContextMenuStrip BuildMenu()
        {
            ContextMenuStrip result=new ContextMenuStrip{Font=new Font("Microsoft YaHei UI",10f),ShowImageMargin=false};
            result.Items.Add(new ToolStripMenuItem(assets.PetName+" · 桌宠陪伴") {Enabled=false});result.Items.Add(new ToolStripSeparator());
            result.Items.Add("通透一下（双击）",null,delegate{Laugh();});
            stopItem=new ToolStripMenuItem("停止播放 / 站起来",null,delegate{if(Motion.Resting){Motion.Stand(Now);RenderNow(true);}else if(Motion.Acting)StopAction();else StopLaugh();});result.Items.Add(stopItem);
            singItem=new ToolStripMenuItem("唱歌",null,delegate{ToggleAction("sing");});result.Items.Add(singItem);
            ToolStripMenuItem actionsMenu=new ToolStripMenuItem("动作");
            actionsMenu.DropDownItems.Add(new ToolStripMenuItem("跳舞",null,delegate{ToggleAction("dance");}));
            actionsMenu.DropDownItems.Add(new ToolStripMenuItem("飞踢",null,delegate{ToggleAction("jump");}));
            actionsMenu.DropDownItems.Add(new ToolStripMenuItem("饿倒",null,delegate{ToggleAction("hungry");}));
            result.Items.Add(actionsMenu);
            soundItem=new ToolStripMenuItem("通透原声",null,delegate{SetSound(!settings.Sound);});result.Items.Add(soundItem);
            result.Items.Add(new ToolStripSeparator());
            ToolStripMenuItem sizes=new ToolStripMenuItem("大小");
            int[] values={65,85,110};string[] labels={"小号","标准","大号"};
            for(int i=0;i<values.Length;i++){int v=values[i];ToolStripMenuItem entry=new ToolStripMenuItem(labels[i],null,delegate{SetSize(v);});entry.Tag=v;sizes.DropDownItems.Add(entry);}result.Items.Add(sizes);
            topItem=new ToolStripMenuItem("总在最上面",null,delegate{TopMost=!TopMost;settings.OnTop=TopMost;Save();UpdateMenu();});result.Items.Add(topItem);
            fullscreenItem=new ToolStripMenuItem("全屏时自动隐藏",null,delegate{SetAutoHide(!settings.AutoHide);});result.Items.Add(fullscreenItem);
            autostartItem=new ToolStripMenuItem("开机自启动",null,delegate{AutoStart=!AutoStart;UpdateMenu();});result.Items.Add(autostartItem);
            randomItem=new ToolStripMenuItem("随机说话",null,delegate{settings.RandomTalk=!settings.RandomTalk;Save();UpdateMenu();});result.Items.Add(randomItem);
            result.Items.Add("编辑台词",null,delegate{EnsureLines();Process.Start(new ProcessStartInfo(LinesPath){UseShellExecute=true});});
            result.Items.Add("回到屏幕右下角",null,delegate{ReturnHome();});
            result.Items.Add("打开使用说明",null,delegate{Process.Start(new ProcessStartInfo(Path.Combine(AppDomain.CurrentDomain.BaseDirectory,"使用说明.txt")){UseShellExecute=true});});
            result.Items.Add(new ToolStripSeparator());result.Items.Add("退出"+assets.PetName,null,delegate{Close();});
            result.Opening+=delegate{menuOpen=true;UpdateMenu();};result.Closed+=delegate{menuOpen=false;SetNoActivate(false);};return result;
        }
        private void UpdateMenu()
        {
            if(menu==null)return;SetToggleMark(soundItem,settings.Sound);soundItem.Enabled=sound!=null;SetToggleMark(topItem,TopMost);
            stopItem.Enabled=Motion.Playing||Motion.Resting||Motion.Acting;
            if(randomItem!=null)SetToggleMark(randomItem,settings.RandomTalk);
            if(autostartItem!=null)SetToggleMark(autostartItem,AutoStart);
            SetToggleMark(fullscreenItem,settings.AutoHide);
            foreach(ToolStripItem entry in menu.Items){ToolStripMenuItem p=entry as ToolStripMenuItem;if(p==null)continue;foreach(ToolStripItem child in p.DropDownItems){ToolStripMenuItem c=child as ToolStripMenuItem;if(c!=null&&c.Tag is int)c.Checked=(int)c.Tag==settings.Scale;}}
        }
        private static void SetToggleMark(ToolStripMenuItem item,bool selected)
        {
            item.Checked=selected;
            // Use the native right-aligned column for status; no shortcut key is assigned.
            item.ShowShortcutKeys=true;item.ShortcutKeyDisplayString=selected?"✓":" ";
        }
        internal void SetSound(bool enabled)
        {
            settings.Sound=enabled&&sound!=null;
            if(!settings.Sound&&sound!=null)sound.Stop();
            // Enabling sound takes effect at the next laugh, so audio never starts out of sync.
            UpdateMenu();Save();
        }
        internal bool Laugh()
        {
            if(HiddenForFullscreen)return false;
            if(Motion.Acting)StopAction();
            if(!Motion.Laugh(Now))return false;
            if(sound!=null&&settings.Sound&&!testing)sound.Play();RenderNow(true);return true;
        }
        internal void StopLaugh(){Motion.Stop();if(sound!=null)sound.Stop();RenderNow(true);}
        // ============ 通用动作系统（sing/dance/jump） ============
        internal void ToggleAction(string name){if(Motion.ActionMode==name)StopAction();else StartAction(name);}
        internal void StartAction(string name)
        {
            if(HiddenForFullscreen||testing)return;
            if(name=="sing"&&!music.HasSongs){ShowGreetingText("把喜欢的歌放进 music 文件夹，重启后我就会唱啦……");return;}
            if(Motion.ActionMode==name)return;
            StopActionAudio(Motion.ActionMode);
            if(Motion.Playing)StopLaugh();
            Motion.StartAction(name,Now);
            if(name=="sing"){assets.CurrentSongFile=Path.GetFileName(music.CurrentSong??"");if(!music.IsPlaying)music.Play(music.Index);UpdateBar();PositionSingBar();singBar.Show();singBar.Visible=true;}
            else if(name=="dance"){if(danceSound!=null)danceSound.Play();}
            else if(name=="jump"){if(jumpSound!=null)jumpSound.Play();}
            else if(name=="hungry"){if(hungrySound!=null)hungrySound.Play();}
            RenderNow(true);
        }
        internal void StopAction()
        {
            string cur=Motion.ActionMode;
            if(cur!=null){Motion.StopAction();StopActionAudio(cur);}
            if(singBar.Visible||music.IsPlaying){music.StopPlay();singBar.Hide();}
            RenderNow(true);
        }
        internal void StopActionAudio(string name)
        {
            if(name=="sing"){if(music.IsPlaying||music.IsPaused)music.StopPlay();if(singBar.Visible)singBar.Hide();}
            else if(name=="dance"){if(danceSound!=null)danceSound.Stop();}
            else if(name=="jump"){if(jumpSound!=null)jumpSound.Stop();}
            else if(name=="hungry"){if(hungrySound!=null)hungrySound.Stop();}
        }
        internal void PlayNextSong(){if(Motion.ActionMode!="sing")return;music.Play(music.Index+1);assets.CurrentSongFile=Path.GetFileName(music.CurrentSong??"");if(singBar.Visible)UpdateBar();}
        internal void UpdateBar(){singBar.UpdateState((Path.GetFileNameWithoutExtension(music.CurrentSong)??"")+" ♪",music.IsPaused);}
        internal void PositionSingBar()
        {
            Rectangle area=Screen.FromRectangle(new Rectangle(Location,Size)).WorkingArea;
            Point p=new Point(Left+Width/2-singBar.Width/2,Bottom+6);
            singBar.Location=new Point(Math.Max(area.Left,Math.Min(p.X,area.Right-singBar.Width)),Math.Max(area.Top,Math.Min(p.Y,area.Bottom-singBar.Height)));
        }
        internal void ShowGreetingText(string text)
        {
            ShowGreetingText(text,9);
        }
        internal void ShowGreetingText(string text,int seconds)
        {
            if(testing||HiddenForFullscreen)return;
            GreetingBubble bubble=new GreetingBubble(text,ContentRect(),seconds);
            bubble.Show(this);
        }
        // 开机自启动：HKCU Run 键，无需管理员权限
        private const string RunKeyPath=@"Software\Microsoft\Windows\CurrentVersion\Run";
        private const string RunValueName="tomorin-pet";
        internal bool AutoStart
        {
            get{try{using(RegistryKey k=Registry.CurrentUser.OpenSubKey(RunKeyPath))return k!=null&&k.GetValue(RunValueName)!=null;}catch{return false;}}
            set{try{using(RegistryKey k=Registry.CurrentUser.CreateSubKey(RunKeyPath)){if(value)k.SetValue(RunValueName,"\""+Application.ExecutablePath+"\"");else k.DeleteValue(RunValueName,false);}}catch{}}
        }
        // 企鹅本体在窗口中的实际位置（窗口上部是透明留白）
        private Rectangle ContentRect()
        {
            RectangleF r=assets.IdleRect;
            return new Rectangle(Left+(int)(Width*r.X),Top+(int)(Height*r.Y),Math.Max(40,(int)(Width*r.Width)),Math.Max(40,(int)(Height*r.Height)));
        }
        private string LinesPath{get{return Path.Combine(Settings.FolderFor(assets.PetId),"lines.txt");}}
        // 所有台词（随机轮播/启动问候/报时）严格从 lines.txt 取；占位符 {time} {hour} {minutes} 运行时替换
        private void EnsureLines()
        {
            try{
                string[] defaults=new string[]{
                    "# 每行一句：随机轮播、启动问候、整点报时都从这里取。# 开头忽略，改完保存下一轮生效。",
                    "# 占位符：{time}=当前时间 {hour}=小时数 {minutes}=陪伴分钟数",
                    "咕咕嘎嘎～",
                    "今天也要通透哦……",
                    "戳戳我的肚子试试？",
                    "双击我，唱通透的那段给你听。",
                    "写代码累了吧……记得喝水。",
                    "初、初次见面……我是凑企鹅。双击我会唱通透的那段……别、别吓到我。",
                    "已经陪伴你 {minutes} 分钟了……今天也、也要通透哦。",
                    "你回来了。……咕。想听歌的话，右键告诉我就好。",
                    "诶……你看到了吗。企鹅今天也在、好好站着呢。",
                    "现在 {time} 啦……企鹅还醒着呢。"};
                if(!File.Exists(LinesPath)){File.WriteAllLines(LinesPath,defaults);return;}
                List<string> have=new List<string>(File.ReadAllLines(LinesPath));
                bool changed=false;
                foreach(string l in defaults){string t=l.Trim();if(t.StartsWith("#"))continue;if(!have.Contains(l)&&!have.Contains(t)){have.Add(l);changed=true;}}
                if(changed)File.WriteAllLines(LinesPath,have);  // 系统默认台词自动迁入已有台词库
            }catch{}
        }
        private string PickLine()
        {
            try{
                if(File.Exists(LinesPath))
                {
                    List<string> pool=new List<string>();
                    foreach(string l in File.ReadAllLines(LinesPath)){string t=l.Trim();if(t.Length>0&&!t.StartsWith("#"))pool.Add(t);}
                    if(pool.Count>0)
                    {
                        string text=pool[rng.Next(pool.Count)];
                        return text.Replace("{time}",DateTime.Now.ToString("HH:mm"))
                                   .Replace("{hour}",DateTime.Now.Hour.ToString())
                                   .Replace("{minutes}",((int)settings.Minutes).ToString());
                    }
                }
            }catch{}
            return null;
        }
        private void RandomPop()
        {
            if(testing||HiddenForFullscreen||menuOpen)return;
            string text=PickLine();
            if(!string.IsNullOrEmpty(text))ShowGreetingText(text,15);
        }
        internal void ShowGreeting()
        {
            if(testing||HiddenForFullscreen)return;
            string text=PickLine();
            if(!string.IsNullOrEmpty(text))ShowGreetingText(text);
        }
        internal void Tick()
        { TickWithForeground(Native.GetForegroundWindow()); }
        internal void TickWithForeground(IntPtr foreground)
        {
            double now=Now;double dt=Math.Min(.05,Math.Max(0,now-lastTickNow));lastTickNow=now;
            if(now>=nextFullscreenCheck){nextFullscreenCheck=now+.12;CheckFullscreenWindow(foreground,false);}
            if(!testing&&now-minuteMark>=60){minuteMark=now;settings.Minutes+=1;if(now-lastMinutesSave>=300){lastMinutesSave=now;Save();}}
            if(!testing&&settings.RandomTalk&&now-lastPop>=150&&!HiddenForFullscreen&&!menuOpen){lastPop=now;RandomPop();}
            // 一次性动作（跳舞/飞踢）播完自动回待机；唱歌无限循环不受此限
            if(Motion.ActionMode!=null&&Motion.ActionMode!="sing"&&now-Motion.ActionStart>=assets.ActionCount(Motion.ActionMode)/assets.ActionFps(Motion.ActionMode))StopAction();
            // 物理甩飞：推进窗口、处理反弹，其余状态暂停
            if(physics.Active&&!HiddenForFullscreen)
            {
                Point next;
                Rectangle area=Screen.FromRectangle(new Rectangle(Location,Size)).WorkingArea;
                physics.Update(Motion,now,dt,Location,Size,area,out next);
                Location=next;
                Motion.DragAngle=Math.Max(-12,Math.Min(12,physics.Vx/90.0));
                if(!physics.Active){Motion.EndFling(now);KeepVisible();Save();RenderNow(true);}
                else RenderNow(false);
                return;
            }
            if(HiddenForFullscreen)return;
            Point p=PointToClient(Cursor.Position);bool over=!menuOpen&&surface.Hit(p.X,p.Y);
            bool wasPlaying=Motion.Playing;Motion.Update(Now,over,assets.Duration,assets.BlinkCount/assets.BlinkFps);
            if(wasPlaying&&!Motion.Playing&&sound!=null)sound.Stop();
            RenderNow(false);
        }
        internal void RenderNow(bool force)
        {
            if(!IsHandleCreated||disposing||HiddenForFullscreen)return;
            string key=Motion.Resting?"R":Motion.Playing?"L"+(int)(Motion.Elapsed*assets.Fps):Motion.Acting?"A"+assets.SeqFor(Motion.ActionMode)+((int)((Motion.Clock-Motion.ActionStart)*assets.ActionFps(Motion.ActionMode))%assets.ActionCount(Motion.ActionMode)):Motion.Blinking?"B"+(Motion.Look>.5?1:0)+"/"+(int)((Motion.Clock-Motion.BlinkStart)*assets.BlinkFps):"E"+(int)Math.Round(Motion.Look*(assets.EyeCount-1));
            if(Motion.Poking||Motion.Moving||Motion.Waking)key+="/M"+(int)(Motion.Clock*60);
            // Idle micro-life: re-render at 24fps so float bob + breathing actually animate.
            if(!Motion.Resting&&!Motion.Playing&&!Motion.Acting&&!Motion.Poking&&!Motion.Moving)key+="/F"+(int)(Motion.Clock*24);
            key+="/"+settings.Scale;
            if(!force&&key==lastVisual)return;
            using(Bitmap frame=Renderer.Render(assets,Motion,settings.Scale))surface.Update(Handle,frame,Location);
            lastVisual=key;
        }
        internal void SetAutoHide(bool value)
        {
            settings.AutoHide=value;fullscreenGate.Reset();
            if(!value)ApplyFullscreen(false);else if(!testing)CheckFullscreen(true);
            Save();UpdateMenu();
        }
        private void CheckFullscreen(bool immediate)
        {CheckFullscreenWindow(Native.GetForegroundWindow(),immediate);}
        private void CheckFullscreenWindow(IntPtr foreground,bool immediate)
        {
            if(!ready||menuOpen||gesture.Pressed)return;
            bool detected=settings.AutoHide&&Fullscreen.IsActive(foreground,Handle,Screen.FromRectangle(Bounds).Bounds);
            if(immediate){fullscreenGate.Set(detected,Now);ApplyFullscreen(detected);}
            else if(fullscreenGate.Update(detected,Now))ApplyFullscreen(fullscreenGate.Hidden);
        }
        internal void ApplyFullscreen(bool hidden)
        {
            if(hidden==HiddenForFullscreen)return;
            HiddenForFullscreen=hidden;
            if(hidden)
            {
                gesture.Cancel();Capture=false;Motion.Suspend(Now);if(sound!=null)sound.Stop();
                physics.Stop();StopAction();
                Hide();timer.Interval=150;
            }
            else
            {
                Motion.Suspend(Now);timer.Interval=16;Show();RenderNow(true);
            }
        }
        private void ReturnHome(){Home();if(!testing)CheckFullscreen(true);if(!HiddenForFullscreen){Show();RenderNow(true);}Save();}
        private Size SizeFor(int scale){return new Size(assets.Width*scale/100,assets.Height*scale/100);}
        internal void SetSize(int scale)
        {
            int center=Left+Width/2,bottom=Top+Height;settings.Scale=Math.Max(50,Math.Min(150,scale));ClientSize=SizeFor(settings.Scale);
            Location=new Point(center-Width/2,bottom-Height);KeepVisible();RenderNow(true);Save();UpdateMenu();
        }
        internal void Home()
        {
            Rectangle area=Screen.FromPoint(Cursor.Position).WorkingArea;
            Location=new Point(area.Right-Width-24,area.Bottom-Height+(int)(12*settings.Scale/100.0));KeepVisible();
        }
        internal static Point Clamp(Point p,Size size,Rectangle area,int allowance)
        {return new Point(Math.Max(area.Left,Math.Min(p.X,area.Right-size.Width)),Math.Max(area.Top,Math.Min(p.Y,area.Bottom-size.Height+allowance)));}
        private void KeepVisible(){Location=Clamp(Location,Size,Screen.FromRectangle(Bounds).WorkingArea,(int)(12*settings.Scale/100.0));}
        private void Save(){if(testing)return;settings.X=Left;settings.Y=Top;settings.Save(assets.PetId);}
        protected override void OnMouseDown(MouseEventArgs e)
        {
            base.OnMouseDown(e);
            if(e.Button==MouseButtons.Right)
            {
                Motion.EndDrag(Now);gesture.Cancel();Capture=false;
                // 临时允许激活：NOACTIVATE 窗口弹菜单会闪任务栏甚至吞菜单，关闭后恢复
                SetNoActivate(true);
                Native.SetForegroundWindow(Handle);
                menu.Show(this,e.Location);
                return;
            }
            if(e.Button!=MouseButtons.Left)return;
            if(physics.Active){physics.Stop();Motion.EndFling(Now);} // 抓住飞行中的企鹅
            gesture.Down(PointToScreen(e.Location));lastDragPointer=gesture.Origin;dragWindow=Location;Capture=true;
        }
        private void SetNoActivate(bool allowActivate)
        {
            int ex=Native.GetWindowLong(Handle,-20);
            int nx=allowActivate?(ex&~0x08000000):(ex|0x08000000);
            if(nx!=ex)Native.SetWindowLong(Handle,-20,nx);
        }
        protected override void OnMouseMove(MouseEventArgs e)
        {
            base.OnMouseMove(e);if(!gesture.Pressed)return;Point p=PointToScreen(e.Location);gesture.Move(p,Now);
            if(gesture.Dragged)
            {
                if(!Motion.Holding){Motion.BeginDrag(Now);if(sound!=null)sound.Stop();}
                Motion.Drag(Now,p.X-lastDragPointer.X);lastDragPointer=p;
                Location=new Point(dragWindow.X+p.X-gesture.Origin.X,dragWindow.Y+p.Y-gesture.Origin.Y);RenderNow(true);
            }
        }
        protected override void OnMouseUp(MouseEventArgs e)
        {
            base.OnMouseUp(e);if(e.Button!=MouseButtons.Left||!gesture.Pressed)return;
            bool moved=gesture.Dragged,twice=gesture.Up(PointToScreen(e.Location),Now);Capture=false;
            if(moved)
            {
                double vx,vy;
                if(!HiddenForFullscreen&&gesture.TryLaunch(out vx,out vy))
                {
                    Motion.LaunchFling(Now);physics.Launch(vx,vy);RenderNow(true);return;
                }
                Motion.EndDrag(Now);KeepVisible();RenderNow(true);Save();
            }
            else if(twice)Laugh();
            else if(Motion.Resting){Motion.Stand(Now);RenderNow(true);}
            else if(Motion.Poke(Now,e.X*100.0/settings.Scale,e.Y*100.0/settings.Scale))RenderNow(true);
        }
        protected override void OnMouseCaptureChanged(EventArgs e){base.OnMouseCaptureChanged(e);if(!Capture&&gesture.Pressed){Motion.EndDrag(Now);gesture.Cancel();KeepVisible();RenderNow(true);Save();}}
        protected override void OnFormClosing(FormClosingEventArgs e){Save();timer.Stop();if(sound!=null)sound.Stop();StopAction();music.Dispose();singBar.Dispose();base.OnFormClosing(e);}
        protected override void Dispose(bool disposingNow)
        {
            if(disposingNow&&!disposing){disposing=true;timer.Dispose();if(tray!=null){tray.Visible=false;tray.Dispose();}if(menu!=null){Font f=menu.Font;menu.Dispose();f.Dispose();}if(sound!=null){sound.Stop();sound.Dispose();}surface.Dispose();if(petIcon!=null)petIcon.Dispose();}
            base.Dispose(disposingNow);
        }
    }

    internal static class Tests
    {
        private static void Check(bool value,string name,List<string> log){if(!value)throw new Exception("FAIL: "+name);log.Add("PASS: "+name);}
        private static void Advance(Motion m,double begin,double end,bool over,Assets a)
        {for(double t=begin;t<=end+.00001;t+=1.0/60)m.Update(t,over,a.Duration,a.BlinkCount/a.BlinkFps);}
        private static bool Equal(Bitmap a,Bitmap b,int fromY,int toY)
        {for(int y=fromY;y<toY;y++)for(int x=0;x<a.Width;x++)if(a.GetPixel(x,y)!=b.GetPixel(x,y))return false;return true;}
        internal static void Run(string folder)
        {
            Directory.CreateDirectory(folder);List<string> log=new List<string>();
            try
            {
                using(Assets a=new Assets(AppDomain.CurrentDomain.BaseDirectory))
                {
                    Check(a.Count==563&&Math.Abs(a.Fps-30)<.01,"563-frame tongtou clip at 30 fps",log);
                    Check(a.Eye(0).GetPixel(0,0).A==0&&a.Eye(1).GetPixel(0,0).A==0,"transparent idle and hover backgrounds",log);
                    // 企鹅 look 帧为静态复用（无眼神跟随差分）：改用眨眼首帧推定眼区范围
                    int eyeTop=int.MaxValue,eyeBottom=int.MinValue;
                    for(int y=0;y<a.Height;y++)for(int x=0;x<a.Width;x++)if(a.Eye(0).GetPixel(x,y)!=a.Blink(0,0).GetPixel(x,y)){if(y<eyeTop)eyeTop=y;if(y>eyeBottom)eyeBottom=y;}
                    Check(eyeTop!=int.MaxValue&&eyeBottom-eyeTop<a.Height*.35,"open-eye blink frame matches idle within a compact eye band",log);
                    byte[] wav=File.ReadAllBytes(a.AudioPath);Check(wav.Length>1000&&Encoding.ASCII.GetString(wav,0,4)=="RIFF","original soundtrack decodes as WAV",log);
                    double blinkDuration=a.BlinkCount/a.BlinkFps;
                    Check(a.BlinkCount==7&&a.BlinkFps==30,"blink uses seven original video frames",log);
                    for(int bank=0;bank<2;bank++)foreach(int f in new[]{0,a.BlinkCount-1})Check(Equal(a.Eye(bank),a.Blink(bank,f),eyeBottom+1,a.Height),"blink end frame preserves body, bank "+bank+" frame "+f,log);
                    Check(!Equal(a.Eye(0),a.Blink(0,3),0,eyeBottom+1),"closed eye differs from open eye",log);
                    Motion m=new Motion((int)a.PokeX,(int)a.PokeY,(int)a.PokeRx,(int)a.PokeRy);Advance(m,0,.3,true,a);Check(m.Look>.999,"hover turns eyes toward pointer",log);
                    Advance(m,.32,.62,false,a);Check(m.Look<.001,"mouse leave restores original eyes",log);
                    Check(m.Laugh(1)&&!m.Laugh(1.01)&&m.PlayCount==1,"double-click playback does not overlap or restart",log);
                    m.Update(1+a.Duration-.05,false,a.Duration,blinkDuration);Check(m.Playing,"complete source clip plays through ending",log);
                    m.Update(1+a.Duration+.01,false,a.Duration,blinkDuration);Check(!m.Playing&&m.Resting,"laugh ends in resting pose",log);
                    m.Update(100,true,a.Duration,blinkDuration);Check(m.Resting&&!m.Blinking,"resting pose stays until clicked",log);
                    m.Stand(100);Check(!m.Resting&&m.Waking,"single click starts standing up",log);Advance(m,100,100.3,false,a);Check(!m.Waking&&!m.Playing,"standing settles to original idle",log);
                    m.Laugh(101);m.Update(101+a.Duration+.001,false,a.Duration,blinkDuration);Check(m.Laugh(120)&&!m.Resting,"can laugh again from resting pose",log);m.Stop();Check(!m.Playing&&!m.Resting,"stop action cancels playback",log);
                    m=new Motion((int)a.PokeX,(int)a.PokeY,(int)a.PokeRx,(int)a.PokeRy);m.Update(4,false,a.Duration,blinkDuration);Check(m.Blinking,"idle schedules a blink",log);
                    m.Update(4+blinkDuration+.01,false,a.Duration,blinkDuration);Check(!m.Blinking&&m.NextBlink>=m.Clock+4&&m.NextBlink<=m.Clock+8,"blink ends and schedules random 4-8 second interval",log);
                    m.Poke(5,(int)a.PokeX,(int)a.PokeY);Check(m.Poking&&!m.Blinking,"poke interrupts blink",log);m.Update(5.1,false,a.Duration,blinkDuration);
                    using(Bitmap warped=Renderer.WarpBelly(a,a.Eye(0),m.PokeX,m.PokeY,m.PokeAmount))
                    {Check(Equal(warped,a.Eye(0),0,(int)a.WarpTop),"belly feedback preserves face",log);Check(!Equal(warped,a.Eye(0),(int)a.WarpTop+20,(int)a.WarpBottom-20),"belly feedback visibly deforms source pixels",log);}
                    Advance(m,5.11,6,false,a);Check(!m.Poking&&Math.Abs(m.PokeAmount)<.0001,"belly rebound settles",log);
                    Check(!m.Poke(6,(int)a.PokeX,(int)(a.PokeY-a.PokeRy*2.2)),"clicking face does not poke belly",log);
                    m.Poke(6,(int)a.PokeX,(int)a.PokeY);m.Laugh(6.1);Check(!m.Poking&&m.Playing,"double click cancels poke before original laugh",log);
                    m.BeginDrag(7);Check(m.Holding&&!m.Playing,"drag interrupts playback",log);
                    for(int i=1;i<=30;i++){m.Drag(7+i/60.0,12);m.Update(7+i/60.0,true,a.Duration,blinkDuration);}
                    Check(m.DragAngle>2&&m.DragAngle<=7,"drag tilts toward movement and stays bounded",log);
                    m.EndDrag(7.5);m.Update(7.57,true,a.Duration,blinkDuration);Check(!m.Holding&&m.Landing&&m.Squash>.01,"release starts landing bounce",log);
                    Advance(m,7.58,9,false,a);Check(!m.Landing&&Math.Abs(m.DragAngle)<.05,"drag and landing settle cleanly",log);
                    Gesture gesture=new Gesture();Point p=new Point(100,100);gesture.Down(p);Check(!gesture.Up(p,1),"single click does not laugh",log);gesture.Down(p);Check(gesture.Up(p,1.12),"double click triggers laugh",log);
                    gesture.Down(p);gesture.Move(new Point(140,160),2);Check(!gesture.Up(new Point(140,160),2),"drag does not trigger laugh",log);
                    gesture.Down(p);Check(!gesture.Up(p,2.1),"drag resets double-click sequence",log);gesture.Cancel();Check(!gesture.Pressed,"cancelled pointer capture releases drag",log);
                    Point clamped=PetWindow.Clamp(new Point(-3000,-50),new Size(245,312),new Rectangle(-1920,0,1920,1040),10);Check(clamped.X==-1920&&clamped.Y==0,"negative-coordinate monitor bounds",log);
                    Rectangle monitor=new Rectangle(0,0,1920,1080);
                    Check(Fullscreen.Covers(monitor,monitor,0,"FullscreenPlayer"),"borderless fullscreen is detected",log);
                    Check(!Fullscreen.Covers(monitor,monitor,0x00c00000,"NormalWindow"),"ordinary maximized window is ignored",log);
                    Check(!Fullscreen.Covers(new Rectangle(0,0,1920,1040),monitor,0,"Video"),"window that leaves taskbar visible is not fullscreen",log);
                    Check(!Fullscreen.Covers(new Rectangle(-1920,0,1920,1080),monitor,0,"Video"),"fullscreen on another monitor is ignored",log);
                    Check(Fullscreen.Covers(new Rectangle(-1920,0,1920,1080),new Rectangle(-1920,0,1920,1080),0,"Video"),"fullscreen works on negative-coordinate monitor",log);
                    Check(!Fullscreen.Covers(monitor,monitor,0,"WorkerW"),"desktop background is not fullscreen app",log);
                    FullscreenGate gate=new FullscreenGate();Check(!gate.Update(true,0)&&!gate.Update(false,.08)&&!gate.Hidden,"brief fullscreen switch does not flash pet",log);
                    gate.Update(true,1);Check(gate.Update(true,1.2)&&gate.Hidden,"stable fullscreen hides pet",log);gate.Update(false,2);Check(gate.Update(false,2.3)&&!gate.Hidden,"leaving fullscreen restores pet",log);
                    using(PetWindow form=new PetWindow(a,true))
                    {
                        form.Show();Application.DoEvents();form.RenderNow(true);
                        Check(Native.IsWindowVisible(form.Handle),"native pet window is visible",log);
                        int style=Native.GetWindowLong(form.Handle,-20);Check((style&0x80000)!=0&&(style&0x80)!=0&&(style&0x08000000)!=0,"alpha transparency, no taskbar entry, no focus stealing",log);
                        form.SetSize(65);Check(form.Width==a.Width*65/100,"small size renders",log);form.SetSize(110);Check(form.Width==a.Width*110/100,"large size renders",log);form.SetSize(85);
                        form.Location=new Point(-50000,-50000);form.SetSize(85);Check(Screen.FromRectangle(form.Bounds).WorkingArea.IntersectsWith(form.Bounds),"lost window position recovers",log);
                        form.SetSound(true);Check(form.SoundEnabled,"original audio switch can be enabled",log);form.SetSound(false);Check(!form.SoundEnabled,"sound switch can be muted",log);
                        IntPtr mousePoint=(IntPtr)(((int)(a.PokeY*.85)<<16)|(int)(a.PokeX*.85));
                        Native.SendMessage(form.Handle,0x201,(IntPtr)1,mousePoint);Native.SendMessage(form.Handle,0x202,IntPtr.Zero,mousePoint);
                        Check(!form.Motion.Playing&&form.Motion.Poking,"native single belly click triggers poke",log);
                        Native.SendMessage(form.Handle,0x203,(IntPtr)1,mousePoint);Native.SendMessage(form.Handle,0x202,IntPtr.Zero,mousePoint);
                        Check(form.Motion.Playing&&!form.Motion.Poking,"native double-click events replace poke with playback",log);form.StopLaugh();
                        form.Motion.Laugh(0);form.Motion.Update(a.Duration,false,a.Duration,blinkDuration);Check(form.Motion.Resting,"native window reaches resting state",log);
                        IntPtr footPoint=(IntPtr)(((int)((a.PokeY-a.PokeRy*2.2)*.85)<<16)|(int)(a.PokeX*.85));
                        Native.SendMessage(form.Handle,0x201,(IntPtr)1,footPoint);Native.SendMessage(form.Handle,0x202,IntPtr.Zero,footPoint);
                        Check(!form.Motion.Resting&&form.Motion.Waking,"native click wakes resting pet",log);form.StopLaugh();
                        Native.SendMessage(form.Handle,0x201,(IntPtr)1,mousePoint);
                        Native.SendMessage(form.Handle,0x200,(IntPtr)1,(IntPtr)((180<<16)|155));Check(form.Motion.Holding,"native drag starts feedback",log);
                        Native.SendMessage(form.Handle,0x202,IntPtr.Zero,mousePoint);Check(!form.Motion.Holding&&form.Motion.Landing&&!form.Motion.Playing,"native drag release bounces without laughing",log);form.StopLaugh();
                        using(Form fullscreen=new Form())
                        {
                            fullscreen.FormBorderStyle=FormBorderStyle.None;fullscreen.StartPosition=FormStartPosition.Manual;fullscreen.ShowInTaskbar=false;fullscreen.Opacity=.01;
                            fullscreen.Bounds=Screen.FromRectangle(form.Bounds).Bounds;fullscreen.Show();Application.DoEvents();
                            Check(Fullscreen.IsActive(fullscreen.Handle,form.Handle,fullscreen.Bounds),"native borderless fullscreen detection",log);
                            Check(!Fullscreen.IsActive(form.Handle,form.Handle,fullscreen.Bounds),"pet window is excluded from fullscreen detection",log);
                            // Supply the actual test HWND; sandbox desktops cannot take foreground focus.
                            form.TickWithForeground(fullscreen.Handle);Thread.Sleep(220);form.TickWithForeground(fullscreen.Handle);Check(form.HiddenForFullscreen&&!Native.IsWindowVisible(form.Handle),"native fullscreen detection automatically hides pet through timer",log);
                            fullscreen.Hide();Check(!Fullscreen.IsActive(fullscreen.Handle,form.Handle,fullscreen.Bounds),"hidden window is excluded from fullscreen detection",log);
                            Thread.Sleep(180);form.TickWithForeground(fullscreen.Handle);Thread.Sleep(300);form.TickWithForeground(fullscreen.Handle);
                            Check(!form.HiddenForFullscreen&&Native.IsWindowVisible(form.Handle),"leaving fullscreen automatically restores pet through timer",log);fullscreen.Close();
                        }
                        Point savedLocation=form.Location;form.Laugh();form.ApplyFullscreen(true);
                        Check(form.HiddenForFullscreen&&!Native.IsWindowVisible(form.Handle)&&!form.Motion.Playing,"fullscreen hides native pet and interrupts playback",log);
                        Check(!form.Laugh(),"hidden pet cannot play audio or laugh",log);
                        form.ApplyFullscreen(false);Check(!form.HiddenForFullscreen&&Native.IsWindowVisible(form.Handle)&&form.Location==savedLocation,"fullscreen exit restores same position",log);
                        form.Motion.Laugh(0);form.Motion.Update(a.Duration,false,a.Duration,blinkDuration);form.ApplyFullscreen(true);form.ApplyFullscreen(false);
                        Check(form.Motion.Resting,"resting pose survives fullscreen hide and restore",log);
                        form.ApplyFullscreen(true);form.SetAutoHide(false);Check(Native.IsWindowVisible(form.Handle)&&!form.HiddenForFullscreen,"disabling automatic hide reveals pet",log);form.StopLaugh();
                        // Fill the bounded cache before measuring steady-state resource use.
                        for(int i=0;i<12;i++)a.Frame(i);
                        int before=Native.GetGuiResources(Process.GetCurrentProcess().Handle,0);Stopwatch sw=Stopwatch.StartNew();
                        form.Motion.Laugh(0);
                        for(int i=0;i<a.Count;i++){form.Motion.Elapsed=i/a.Fps;form.RenderNow(true);}
                        sw.Stop();int after=Native.GetGuiResources(Process.GetCurrentProcess().Handle,0);
                        log.Add("METRIC: all-frame decode/render average "+(sw.Elapsed.TotalMilliseconds/a.Count).ToString("F2")+" ms; GDI delta "+(after-before));
                        // GDI+ lazily initializes renderer resources on its first complete playback.
                        for(int i=0;i<a.Count;i++){form.Motion.Elapsed=i/a.Fps;form.RenderNow(true);}
                        int stable=Native.GetGuiResources(Process.GetCurrentProcess().Handle,0);
                        log.Add("METRIC: repeat-playback GDI delta "+(stable-after));
                        Check(stable-after<10,"repeat playback does not leak GDI handles",log);Check(a.CacheCount<=12,"decoded frame cache stays bounded",log);
                        form.Motion.Stop();form.RenderNow(true);form.Close();Check(form.IsDisposed,"window closes cleanly",log);
                    }
                    using(Icon icon=Renderer.CreateIcon(a))using(FileStream f=File.Create(Path.Combine(folder,"naiwa.ico")))icon.Save(f);
                    m=new Motion((int)a.PokeX,(int)a.PokeY,(int)a.PokeRx,(int)a.PokeRy);
                    using(Bitmap b=Renderer.Render(a,m,100))b.Save(Path.Combine(folder,"native-idle.png"),ImageFormat.Png);
                    m.Look=1;using(Bitmap b=Renderer.Render(a,m,100))b.Save(Path.Combine(folder,"native-hover.png"),ImageFormat.Png);
                    m.Laugh(0);m.Elapsed=1;using(Bitmap b=Renderer.Render(a,m,100))b.Save(Path.Combine(folder,"native-laugh.png"),ImageFormat.Png);
                    m=new Motion((int)a.PokeX,(int)a.PokeY,(int)a.PokeRx,(int)a.PokeRy);m.Poke(0,(int)a.PokeX,(int)a.PokeY-6);m.Update(.10,false,a.Duration,blinkDuration);using(Bitmap b=Renderer.Render(a,m,100))b.Save(Path.Combine(folder,"native-poke.png"),ImageFormat.Png);
                    m.BeginDrag(1);m.DragAngle=6;using(Bitmap b=Renderer.Render(a,m,100))b.Save(Path.Combine(folder,"native-drag.png"),ImageFormat.Png);
                    m=new Motion();m.BlinkStart=0;m.Clock=.1;using(Bitmap b=Renderer.Render(a,m,100))b.Save(Path.Combine(folder,"native-blink.png"),ImageFormat.Png);
                    m.Stop();m.Resting=true;using(Bitmap b=Renderer.Render(a,m,100))b.Save(Path.Combine(folder,"native-rest.png"),ImageFormat.Png);
                }
                log.Add("RESULT: PASS");
            }
            catch(Exception e){log.Add(e.ToString());log.Add("RESULT: FAIL");Environment.ExitCode=1;}
            File.WriteAllLines(Path.Combine(folder,"self-test.txt"),log.ToArray(),Encoding.UTF8);
        }
        internal static void Demo(string folder)
        {
            Directory.CreateDirectory(folder);using(Assets a=new Assets(AppDomain.CurrentDomain.BaseDirectory))
            {
                Motion m=new Motion((int)a.PokeX,(int)a.PokeY,(int)a.PokeRx,(int)a.PokeRy);m.NextBlink=.6;
                for(int i=0;i<720;i++)
                {
                    double t=i/30.0;
                    if(i==60)m.Poke(t,(int)a.PokeX,(int)a.PokeY-6);
                    if(i==90)m.BeginDrag(t);
                    if(i>=90&&i<126)m.Drag(t,i<108?5:-5);
                    if(i==126)m.EndDrag(t);
                    if(i==174)m.Laugh(t);
                    if(i==666)m.Stand(t);
                    m.Update(t,t>=1.1&&t<5.8,a.Duration,a.BlinkCount/a.BlinkFps);
                    using(Bitmap b=Renderer.Render(a,m,100))b.Save(Path.Combine(folder,i.ToString("0000")+".png"),ImageFormat.Png);
                }
            }
        }
    }
}
