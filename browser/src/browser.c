// SPDX-License-Identifier: GPL-3.0-or-later
#define _GNU_SOURCE
#include <wpe/webkit.h>
#include <wpe/wpe-platform.h>
#include <wpe/headless/wpe-headless.h>
#include <jsc/jsc.h>
#include <glib-unix.h>
#include <fcntl.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

static GMainLoop *loop;
static JSCContext *json;
static WebKitWebView *web;
static WPEView *view;
static GBytes *pending;
static int width, height;
static guint stride;
static char *proxy_user, *proxy_password;
static gboolean (*headless_render)(WPEView *, WPEBuffer *, const WPERectangle *, guint, GError **);
static char *quote(const char *s) {
    JSCValue *v=jsc_value_new_string(json,s?s:""); char *out=jsc_value_to_json(v,0); g_object_unref(v); return out;
}
static char *string(JSCValue *v,const char *name) {
    JSCValue *p=jsc_value_object_get_property(v,name);
    char *s=jsc_value_is_string(p)?jsc_value_to_string(p):g_strdup(""); g_object_unref(p); return s;
}
static double number(JSCValue *v,const char *name) {
    JSCValue *p=jsc_value_object_get_property(v,name); double n=jsc_value_to_double(p); g_object_unref(p); return n;
}
static void error_message(const char *message) { g_autofree char *q=quote(message); g_print("{\"event\":\"error\",\"message\":%s}\n",q); }
static void status(void) {
    g_autofree char *url=quote(webkit_web_view_get_uri(web)), *title=quote(webkit_web_view_get_title(web));
    g_print("{\"event\":\"status\",\"url\":%s,\"title\":%s,\"loading\":%s,\"back\":%s,\"forward\":%s}\n",url,title,
        webkit_web_view_is_loading(web)?"true":"false",webkit_web_view_can_go_back(web)?"true":"false",webkit_web_view_can_go_forward(web)?"true":"false");
}
static void notify(GObject *obj,GParamSpec *pspec,gpointer data) { (void)obj;(void)pspec;(void)data;status(); }
static gboolean render(WPEView *v,WPEBuffer *b,const WPERectangle *damage,guint count,GError **error) {
    if(WPE_IS_BUFFER_SHM(b)) {
        g_clear_pointer(&pending,g_bytes_unref); pending=g_bytes_ref(wpe_buffer_shm_get_data(WPE_BUFFER_SHM(b)));
        width=wpe_buffer_get_width(b);height=wpe_buffer_get_height(b);stride=wpe_buffer_shm_get_stride(WPE_BUFFER_SHM(b));
    }
    return headless_render(v,b,damage,count,error);
}
static gboolean flush_frame(gpointer data) {
    (void)data;if(!pending)return G_SOURCE_CONTINUE;
    gsize n;const char *bytes=g_bytes_get_data(pending,&n);
    GError *error=NULL;
    if(g_file_set_contents("/output/view.tmp",bytes,n,&error) && !rename("/output/view.tmp","/output/view.bgra"))
        g_print("{\"event\":\"frame\",\"w\":%d,\"h\":%d,\"stride\":%u}\n",width,height,stride);
    else { g_printerr("Frame export: %s\n",error?error->message:"rename failed");g_clear_error(&error); }
    g_clear_pointer(&pending,g_bytes_unref);return G_SOURCE_CONTINUE;
}
static void send(WPEEvent *event) { wpe_view_event(view,event);wpe_event_unref(event); }
static void key(guint code,guint val,WPEModifiers mods) {
    guint32 t=g_get_monotonic_time()/1000;
    send(wpe_event_keyboard_new(WPE_EVENT_KEYBOARD_KEY_DOWN,view,WPE_INPUT_SOURCE_KEYBOARD,t,mods,code,val));
    send(wpe_event_keyboard_new(WPE_EVENT_KEYBOARD_KEY_UP,view,WPE_INPUT_SOURCE_KEYBOARD,t+1,mods,code,val));
}
static gboolean safe_url(const char *url) { return g_str_has_prefix(url,"https://") || g_str_has_prefix(url,"http://") || !strcmp(url,"file:///opt/wpe/start.html"); }
static void focus_message(WebKitUserContentManager *manager,JSCValue *value,gpointer unused) {
    (void)manager;(void)unused;g_autofree char *s=jsc_value_to_json(value,0);
    if(s && strlen(s)<65536)g_print("{\"event\":\"focus\",\"field\":%s}\n",s);
}
static gboolean decide_destination(WebKitDownload *download,const char *suggested,gpointer data) {
    (void)data;g_autofree char *name=g_path_get_basename(suggested?suggested:"download");
    if(!strcmp(name,".") || !strcmp(name,"..") || !*name){g_free(g_steal_pointer(&name));name=g_strdup("download");}
    for(char *p=name;*p;p++)if((unsigned char)*p<32 || *p=='/' || *p=='\\')*p='_';
    g_autofree char *path=NULL;
    for(unsigned i=0;i<10000;i++) {
        g_free(g_steal_pointer(&path));path=i?g_strdup_printf("/downloads/%u-%s",i,name):g_strdup_printf("/downloads/%s",name);
        int fd=open(path,O_WRONLY|O_CREAT|O_EXCL|O_CLOEXEC,0664);
        if(fd>=0){close(fd);break;}
        if(i==9999){webkit_download_cancel(download);return TRUE;}
    }
    webkit_download_set_allow_overwrite(download,TRUE);webkit_download_set_destination(download,path);
    return TRUE;
}
static void download_progress(WebKitDownload *d,GParamSpec *pspec,gpointer data) {
    (void)pspec;(void)data;g_autofree char *name=quote(webkit_download_get_destination(d));
    g_print("{\"event\":\"download\",\"name\":%s,\"progress\":%.3f,\"bytes\":%llu}\n",name,webkit_download_get_estimated_progress(d),(unsigned long long)webkit_download_get_received_data_length(d));
}
static void download_failed(WebKitDownload *d,GError *error,gpointer data) {(void)data;g_object_set_data(G_OBJECT(d),"failed",GINT_TO_POINTER(1));error_message(error->message);}
static void download_finished(WebKitDownload *d,gpointer data) {(void)data;if(g_object_get_data(G_OBJECT(d),"failed"))return;g_autofree char *name=quote(webkit_download_get_destination(d));g_print("{\"event\":\"download_done\",\"name\":%s,\"bytes\":%llu}\n",name,(unsigned long long)webkit_download_get_received_data_length(d));}
static void download_started(WebKitNetworkSession *session,WebKitDownload *d,gpointer data) {
    (void)session;(void)data;g_signal_connect(d,"decide-destination",G_CALLBACK(decide_destination),NULL);
    g_signal_connect(d,"notify::estimated-progress",G_CALLBACK(download_progress),NULL);
    g_signal_connect(d,"failed",G_CALLBACK(download_failed),NULL);g_signal_connect(d,"finished",G_CALLBACK(download_finished),NULL);
}
static gboolean policy(WebKitWebView *v,WebKitPolicyDecision *d,WebKitPolicyDecisionType type,gpointer data) {
    (void)data;
    if(type==WEBKIT_POLICY_DECISION_TYPE_NAVIGATION_ACTION || type==WEBKIT_POLICY_DECISION_TYPE_NEW_WINDOW_ACTION) {
        WebKitNavigationAction *a=webkit_navigation_policy_decision_get_navigation_action(WEBKIT_NAVIGATION_POLICY_DECISION(d));
        const char *uri=webkit_uri_request_get_uri(webkit_navigation_action_get_request(a));
        if(!safe_url(uri)){webkit_policy_decision_ignore(d);return TRUE;}
        if(type==WEBKIT_POLICY_DECISION_TYPE_NEW_WINDOW_ACTION){webkit_web_view_load_uri(v,uri);webkit_policy_decision_ignore(d);return TRUE;}
    } else if(type==WEBKIT_POLICY_DECISION_TYPE_RESPONSE && !webkit_response_policy_decision_is_mime_type_supported(WEBKIT_RESPONSE_POLICY_DECISION(d))) {
        webkit_policy_decision_download(d);return TRUE;
    }
    return FALSE;
}
static gboolean failed(WebKitWebView *v,WebKitLoadEvent event,const char *uri,GError *error,gpointer data) {
    (void)v;(void)event;(void)uri;(void)data;
    if(!g_error_matches(error,WEBKIT_NETWORK_ERROR,WEBKIT_NETWORK_ERROR_CANCELLED))error_message(error->message);
    return FALSE;
}
static void terminated(WebKitWebView *v,WebKitWebProcessTerminationReason reason,gpointer data) {(void)v;(void)data;g_autofree char *s=g_strdup_printf("Web process stopped (%d). Reload to retry.",reason);error_message(s);}
static gboolean authenticate(WebKitWebView *v,WebKitAuthenticationRequest *r,gpointer data) {
    (void)v;(void)data;
    if(webkit_authentication_request_is_for_proxy(r) && proxy_user && !webkit_authentication_request_is_retry(r)) {
        WebKitCredential *c=webkit_credential_new(proxy_user,proxy_password,WEBKIT_CREDENTIAL_PERSISTENCE_NONE);
        webkit_authentication_request_authenticate(r,c);webkit_credential_free(c);return TRUE;
    }
    webkit_authentication_request_cancel(r);error_message("HTTP authentication is required.");return TRUE;
}
static void configure(JSCValue *v) {
    g_autofree char *uri=string(v,"proxy");
    g_free(proxy_user);g_free(proxy_password);proxy_user=string(v,"username");proxy_password=string(v,"password");
    WebKitNetworkSession *s=webkit_web_view_get_network_session(web);
    if(*uri && proxy_user && *proxy_user) {
        char *separator=strstr(uri,"://");
        if(separator) {
            g_autofree char *user=g_uri_escape_string(proxy_user,NULL,FALSE);
            g_autofree char *password=g_uri_escape_string(proxy_password,NULL,FALSE);
            char *authenticated=g_strdup_printf("%.*s://%s:%s@%s",(int)(separator-uri),uri,user,password,separator+3);
            g_free(uri);uri=authenticated;
        }
    }
    if(*uri){WebKitNetworkProxySettings *p=webkit_network_proxy_settings_new(uri,NULL);webkit_network_session_set_proxy_settings(s,WEBKIT_NETWORK_PROXY_MODE_CUSTOM,p);webkit_network_proxy_settings_free(p);}
    else webkit_network_session_set_proxy_settings(s,WEBKIT_NETWORK_PROXY_MODE_NO_PROXY,NULL);
}
static gboolean command(GIOChannel *ch,GIOCondition condition,gpointer data) {
    (void)data;
    if(condition & (G_IO_HUP|G_IO_ERR)){g_main_loop_quit(loop);return G_SOURCE_REMOVE;}
    for (;;) {
    char *line=NULL;gsize size;GError *error=NULL;
    GIOStatus result=g_io_channel_read_line(ch,&line,&size,NULL,&error);
    if(result!=G_IO_STATUS_NORMAL){g_clear_error(&error);g_free(line);return G_SOURCE_CONTINUE;}
    if(size>65536){g_free(line);return G_SOURCE_CONTINUE;}
    JSCValue *v=jsc_value_new_from_json(json,line);g_free(line);
    if(!v || !jsc_value_is_object(v)){g_clear_object(&v);return G_SOURCE_CONTINUE;}
    g_autofree char *cmd=string(v,"cmd");
    if(!strcmp(cmd,"close"))g_main_loop_quit(loop);
    else if(!strcmp(cmd,"configure"))configure(v);
    else if(!strcmp(cmd,"navigate")){g_autofree char *uri=string(v,"url");if(safe_url(uri))webkit_web_view_load_uri(web,uri);}
    else if(!strcmp(cmd,"back"))webkit_web_view_go_back(web);
    else if(!strcmp(cmd,"forward"))webkit_web_view_go_forward(web);
    else if(!strcmp(cmd,"reload"))webkit_web_view_reload(web);
    else if(!strcmp(cmd,"focus"))webkit_web_view_evaluate_javascript(web,"window.__skywardReportFocus && window.__skywardReportFocus()",-1,"skyward",NULL,NULL,NULL,NULL);
    else if(!strcmp(cmd,"text")) {
        g_autofree char *text=string(v,"text");key(30,'a',WPE_MODIFIER_KEYBOARD_CONTROL);key(14,0xff08,0);
        for(const char *p=text;*p;p=g_utf8_next_char(p)){gunichar c=g_utf8_get_char(p);key(0,c<256?c:0x01000000|c,0);}
    } else if(!strcmp(cmd,"touch")) {
        int phase=number(v,"phase");double x=number(v,"x"),y=number(v,"y");
        if(phase>=0 && phase<=2)send(wpe_event_touch_new(phase==0?WPE_EVENT_TOUCH_DOWN:phase==1?WPE_EVENT_TOUCH_MOVE:WPE_EVENT_TOUCH_UP,
            view,WPE_INPUT_SOURCE_TOUCHSCREEN,g_get_monotonic_time()/1000,0,1,x,y));
    }
    g_object_unref(v);
    }
}
int main(int argc,char **argv) {
    setvbuf(stdout,NULL,_IOLBF,0);
    int w=argc>1?atoi(argv[1]):800,h=argc>2?atoi(argv[2]):1000;
    if(w<200 || w>1600 || h<200 || h>2560)return 2;
    GError *error=NULL;WPEDisplay *display=wpe_display_headless_new();
    if(!wpe_display_connect(display,&error)){g_printerr("Display: %s\n",error->message);return 2;}
    web=g_object_new(WEBKIT_TYPE_WEB_VIEW,"display",display,NULL);
    json=jsc_context_new();
    WebKitNetworkSession *session=webkit_web_view_get_network_session(web);
    WebKitSettings *settings=webkit_web_view_get_settings(web);
    webkit_settings_set_enable_media(settings,FALSE);webkit_settings_set_enable_webgl(settings,FALSE);
    view=webkit_web_view_get_wpe_view(web);WPEViewClass *klass=WPE_VIEW_GET_CLASS(view);headless_render=klass->render_buffer;klass->render_buffer=render;
    WPEToplevel *top=wpe_view_get_toplevel(view);wpe_toplevel_resize(top,w,h);wpe_view_resized(view,w,h);wpe_view_map(view);wpe_view_focus_in(view);
    WebKitUserContentManager *manager=webkit_web_view_get_user_content_manager(web);
    webkit_user_content_manager_register_script_message_handler(manager,"skyward","skyward");
    g_signal_connect(manager,"script-message-received::skyward",G_CALLBACK(focus_message),NULL);
    const char *source="window.__skywardReportFocus=()=>{let e=document.activeElement;if(!e)return;let type=(e.type||'').toLowerCase();if(e.tagName==='TEXTAREA'||e.isContentEditable||(e.tagName==='INPUT'&&!['button','submit','reset','checkbox','radio','range','color','file','hidden'].includes(type))){window.webkit.messageHandlers.skyward.postMessage({text:(e.value||e.textContent||'').slice(0,8192),secret:type==='password'});}};document.addEventListener('focusin',window.__skywardReportFocus,true);";
    WebKitUserScript *script=webkit_user_script_new_for_world(source,WEBKIT_USER_CONTENT_INJECT_ALL_FRAMES,WEBKIT_USER_SCRIPT_INJECT_AT_DOCUMENT_START,"skyward",NULL,NULL);
    webkit_user_content_manager_add_script(manager,script);webkit_user_script_unref(script);
    g_signal_connect(web,"notify::uri",G_CALLBACK(notify),NULL);g_signal_connect(web,"notify::title",G_CALLBACK(notify),NULL);g_signal_connect(web,"notify::is-loading",G_CALLBACK(notify),NULL);
    g_signal_connect(web,"load-failed",G_CALLBACK(failed),NULL);g_signal_connect(web,"decide-policy",G_CALLBACK(policy),NULL);g_signal_connect(web,"web-process-terminated",G_CALLBACK(terminated),NULL);g_signal_connect(web,"authenticate",G_CALLBACK(authenticate),NULL);
    g_signal_connect(session,"download-started",G_CALLBACK(download_started),NULL);
    GIOChannel *in=g_io_channel_unix_new(STDIN_FILENO);g_io_channel_set_flags(in,G_IO_FLAG_NONBLOCK,NULL);g_io_add_watch(in,G_IO_IN|G_IO_HUP|G_IO_ERR,command,NULL);
    loop=g_main_loop_new(NULL,FALSE);g_timeout_add(80,flush_frame,NULL);
    char *html=NULL;
    if(!g_file_get_contents("/opt/wpe/start.html",&html,NULL,&error)){g_printerr("Start page: %s\n",error->message);return 2;}
    webkit_web_view_load_html(web,html,"file:///opt/wpe/start.html");g_free(html);g_main_loop_run(loop);
    return 0;
}
