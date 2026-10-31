using System;
using System.Diagnostics;
using System.Drawing;
using System.IO;
namespace NaiwaDesktop
{
    internal static class AssetsTester
    {
        private static void Main()
        {
            Environment.CurrentDirectory=AppDomain.CurrentDomain.BaseDirectory;
            using(Assets a=new Assets(AppDomain.CurrentDomain.BaseDirectory))
            {
                Console.WriteLine("SongSeq 条目:"+a.SongSeq.Count);
                foreach(System.Collections.Generic.KeyValuePair<string,string> kv in a.SongSeq)Console.WriteLine("  "+kv.Key+" -> "+kv.Value);
                foreach(string song in new string[]{"billie jean.m4a","cry for me.m4a","雨爱.m4a","九万字.m4a","just two of us.m4a","L的小曲.m4a"})
                {
                    a.CurrentSongFile=song;
                    Console.WriteLine(song+" -> "+a.SeqFor("sing")+" count="+a.ActionCount("sing")+" fps="+a.ActionFps("sing"));
                }
                Console.WriteLine("dance="+a.ActionCount("dance")+" jump="+a.ActionCount("jump"));
                // 懒加载全量校验：每个序列的首/中/末帧都要能从素材包按需解码
                Check("laugh",a.Count,i=>a.Frame(i),a);
                if(a.HasSing)Check("sing",a.SingCount,i=>a.SingFrame(i),a);
                foreach(string bank in new string[]{"dance","jump","mic","turn","hungry","closeup","yuai","qn","pyj","tongtou"})
                {
                    int n=a.ActionCount(bank);
                    if(n<2){Console.WriteLine("  "+bank+": 无序列，跳过");continue;}
                    Check(bank,n,i=>a.ActionFrame(bank,i),a);
                }
                // 冷读延迟：顺序解码 dance 前 60 帧（LRU 必然逐帧冷读），对比 15fps 的 66ms 帧预算
                Stopwatch sw=Stopwatch.StartNew();
                for(int i=0;i<60;i++)a.ActionFrame("dance",i);
                sw.Stop();
                Console.WriteLine("dance 顺序冷读平均 {0:F1} ms/帧（预算 66ms）",sw.Elapsed.TotalMilliseconds/60);
                Console.WriteLine("ALL BANKS OK");
            }
        }
        private static void Check(string name,int count,Func<int,Bitmap> frame,Assets a)
        {
            foreach(int i in new int[]{0,count/2,count-1})
            using(Bitmap b=frame(i))
            {
                if(b.Width!=a.Width||b.Height!=a.Height)throw new Exception(name+" 帧"+i+"尺寸异常");
                int opaque=0;for(int y=0;y<b.Height;y+=7)for(int x=0;x<b.Width;x+=7)if(b.GetPixel(x,y).A>200)opaque++;
                Console.WriteLine("  "+name+" 帧"+i+": 不透明采样点 "+opaque);
            }
            Console.WriteLine("  "+name+": "+count+" 帧 首/中/末 OK");
        }
    }
}
