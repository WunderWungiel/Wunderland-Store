--
-- PostgreSQL database dump
--

-- Dumped from database version 16.2 (Debian 16.2-1.pgdg120+2)
-- Dumped by pg_dump version 16.2 (Debian 16.2-1.pgdg120+2)

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: apps; Type: TABLE; Schema: public; Owner: wunder
--

CREATE TABLE public.apps (
    id integer NOT NULL,
    title character varying DEFAULT 'App'::character varying,
    file character varying DEFAULT '#'::character varying,
    category integer DEFAULT 1,
    description character varying DEFAULT 'Description'::character varying,
    publisher character varying DEFAULT 'Publisher'::character varying,
    version character varying DEFAULT '1.00(0)'::character varying,
    platform character varying NOT NULL,
    screenshots_count integer DEFAULT 0,
    img character varying DEFAULT 'Store.png'::character varying,
    visible boolean DEFAULT true,
    addon_message character varying,
    addon_file character varying,
    uid character varying
);


ALTER TABLE public.apps OWNER TO wunder;

--
-- Name: apps_categories; Type: TABLE; Schema: public; Owner: wunder
--

CREATE TABLE public.apps_categories (
    id integer NOT NULL,
    name character varying NOT NULL
);


ALTER TABLE public.apps_categories OWNER TO wunder;

--
-- Name: apps_categories_id_seq; Type: SEQUENCE; Schema: public; Owner: wunder
--

CREATE SEQUENCE public.apps_categories_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.apps_categories_id_seq OWNER TO wunder;

--
-- Name: apps_categories_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: wunder
--

ALTER SEQUENCE public.apps_categories_id_seq OWNED BY public.apps_categories.id;


--
-- Name: apps_id_seq; Type: SEQUENCE; Schema: public; Owner: wunder
--

CREATE SEQUENCE public.apps_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.apps_id_seq OWNER TO wunder;

--
-- Name: apps_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: wunder
--

ALTER SEQUENCE public.apps_id_seq OWNED BY public.apps.id;


--
-- Name: apps_rating; Type: TABLE; Schema: public; Owner: wunder
--

CREATE TABLE public.apps_rating (
    id integer NOT NULL,
    content_id integer NOT NULL,
    rating integer NOT NULL,
    user_id integer NOT NULL
);


ALTER TABLE public.apps_rating OWNER TO wunder;

--
-- Name: apps_rating_id_seq; Type: SEQUENCE; Schema: public; Owner: wunder
--

CREATE SEQUENCE public.apps_rating_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.apps_rating_id_seq OWNER TO wunder;

--
-- Name: apps_rating_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: wunder
--

ALTER SEQUENCE public.apps_rating_id_seq OWNED BY public.apps_rating.id;


--
-- Name: games; Type: TABLE; Schema: public; Owner: wunder
--

CREATE TABLE public.games (
    id integer NOT NULL,
    title character varying DEFAULT 'Game'::character varying,
    file character varying DEFAULT '#'::character varying,
    category integer DEFAULT 1,
    description character varying DEFAULT 'Description'::character varying,
    publisher character varying DEFAULT 'Publisher'::character varying,
    version character varying DEFAULT '1.00(0)'::character varying,
    platform character varying NOT NULL,
    screenshots_count integer DEFAULT 0,
    img character varying DEFAULT 'Store.png'::character varying,
    visible boolean DEFAULT true,
    addon_message character varying,
    addon_file character varying,
    uid character varying
);


ALTER TABLE public.games OWNER TO wunder;

--
-- Name: games_categories; Type: TABLE; Schema: public; Owner: wunder
--

CREATE TABLE public.games_categories (
    id integer NOT NULL,
    name character varying NOT NULL
);


ALTER TABLE public.games_categories OWNER TO wunder;

--
-- Name: games_categories_id_seq; Type: SEQUENCE; Schema: public; Owner: wunder
--

CREATE SEQUENCE public.games_categories_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.games_categories_id_seq OWNER TO wunder;

--
-- Name: games_categories_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: wunder
--

ALTER SEQUENCE public.games_categories_id_seq OWNED BY public.games_categories.id;


--
-- Name: games_id_seq; Type: SEQUENCE; Schema: public; Owner: wunder
--

CREATE SEQUENCE public.games_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.games_id_seq OWNER TO wunder;

--
-- Name: games_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: wunder
--

ALTER SEQUENCE public.games_id_seq OWNED BY public.games.id;


--
-- Name: platforms; Type: TABLE; Schema: public; Owner: wunder
--

CREATE TABLE public.platforms (
    id character varying NOT NULL,
    name character varying NOT NULL
);


ALTER TABLE public.platforms OWNER TO wunder;

--
-- Name: themes; Type: TABLE; Schema: public; Owner: wunder
--

CREATE TABLE public.themes (
    id integer NOT NULL,
    title character varying DEFAULT 'Theme'::character varying,
    file character varying DEFAULT '#'::character varying,
    category integer DEFAULT 1,
    description character varying DEFAULT 'Description'::character varying,
    publisher character varying DEFAULT 'Publisher'::character varying,
    version character varying DEFAULT '1.00(0)'::character varying,
    platform character varying NOT NULL,
    screenshots_count integer DEFAULT 0,
    img character varying DEFAULT 'Store.png'::character varying,
    visible boolean DEFAULT true
);


ALTER TABLE public.themes OWNER TO wunder;

--
-- Name: themes_categories; Type: TABLE; Schema: public; Owner: wunder
--

CREATE TABLE public.themes_categories (
    id integer NOT NULL,
    name character varying NOT NULL
);


ALTER TABLE public.themes_categories OWNER TO wunder;

--
-- Name: themes_categories_id_seq; Type: SEQUENCE; Schema: public; Owner: wunder
--

CREATE SEQUENCE public.themes_categories_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.themes_categories_id_seq OWNER TO wunder;

--
-- Name: themes_categories_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: wunder
--

ALTER SEQUENCE public.themes_categories_id_seq OWNED BY public.themes_categories.id;


--
-- Name: themes_id_seq; Type: SEQUENCE; Schema: public; Owner: wunder
--

CREATE SEQUENCE public.themes_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.themes_id_seq OWNER TO wunder;

--
-- Name: themes_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: wunder
--

ALTER SEQUENCE public.themes_id_seq OWNED BY public.themes.id;


--
-- Name: users; Type: TABLE; Schema: public; Owner: wunder
--

CREATE TABLE public.users (
    id integer NOT NULL,
    email character varying(100) NOT NULL,
    password character varying NOT NULL,
    active boolean DEFAULT true,
    confirmed boolean DEFAULT false,
    banned boolean DEFAULT false,
    banned_reason character varying DEFAULT ''::character varying,
    username character varying NOT NULL
);


ALTER TABLE public.users OWNER TO wunder;

--
-- Name: users_id_seq; Type: SEQUENCE; Schema: public; Owner: wunder
--

CREATE SEQUENCE public.users_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.users_id_seq OWNER TO wunder;

--
-- Name: users_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: wunder
--

ALTER SEQUENCE public.users_id_seq OWNED BY public.users.id;


--
-- Name: apps id; Type: DEFAULT; Schema: public; Owner: wunder
--

ALTER TABLE ONLY public.apps ALTER COLUMN id SET DEFAULT nextval('public.apps_id_seq'::regclass);


--
-- Name: apps_categories id; Type: DEFAULT; Schema: public; Owner: wunder
--

ALTER TABLE ONLY public.apps_categories ALTER COLUMN id SET DEFAULT nextval('public.apps_categories_id_seq'::regclass);


--
-- Name: apps_rating id; Type: DEFAULT; Schema: public; Owner: wunder
--

ALTER TABLE ONLY public.apps_rating ALTER COLUMN id SET DEFAULT nextval('public.apps_rating_id_seq'::regclass);


--
-- Name: games id; Type: DEFAULT; Schema: public; Owner: wunder
--

ALTER TABLE ONLY public.games ALTER COLUMN id SET DEFAULT nextval('public.games_id_seq'::regclass);


--
-- Name: games_categories id; Type: DEFAULT; Schema: public; Owner: wunder
--

ALTER TABLE ONLY public.games_categories ALTER COLUMN id SET DEFAULT nextval('public.games_categories_id_seq'::regclass);


--
-- Name: themes id; Type: DEFAULT; Schema: public; Owner: wunder
--

ALTER TABLE ONLY public.themes ALTER COLUMN id SET DEFAULT nextval('public.themes_id_seq'::regclass);


--
-- Name: themes_categories id; Type: DEFAULT; Schema: public; Owner: wunder
--

ALTER TABLE ONLY public.themes_categories ALTER COLUMN id SET DEFAULT nextval('public.themes_categories_id_seq'::regclass);


--
-- Name: users id; Type: DEFAULT; Schema: public; Owner: wunder
--

ALTER TABLE ONLY public.users ALTER COLUMN id SET DEFAULT nextval('public.users_id_seq'::regclass);


--
-- Data for Name: apps; Type: TABLE DATA; Schema: public; Owner: wunder
--

COPY public.apps (id, title, file, category, description, publisher, version, platform, screenshots_count, img, visible, addon_message, addon_file) FROM stdin;
1	App	#	1	Description	Publisher	1.00(0)	s60	0	Store.png	t	\N	\N
2	3D Compass	3D Compass v1.00(6).sisx	1	You will always know where you are heading,because 3D Compass shows you the magnetic north with a cool 3D effect! 3D Compass lets you also choose locations from your Nokia Maps landmarks list and a pointy arrow will guide you all the way. You can select the appearance of the compass from several theme options.	BH Production	1.00(6)	s60	0	3DCompass.png	t	Fix below:	XD
\.


--
-- Data for Name: apps_categories; Type: TABLE DATA; Schema: public; Owner: wunder
--

COPY public.apps_categories (id, name) FROM stdin;
1	Other apps
\.


--
-- Data for Name: apps_rating; Type: TABLE DATA; Schema: public; Owner: wunder
--

COPY public.apps_rating (id, content_id, rating, user_id) FROM stdin;
3	1	1	3
2	1	5	2
4	2	1	2
\.


--
-- Data for Name: games; Type: TABLE DATA; Schema: public; Owner: wunder
--

COPY public.games (id, title, file, category, description, publisher, version, platform, screenshots_count, img, visible, addon_message, addon_file) FROM stdin;
\.


--
-- Data for Name: games_categories; Type: TABLE DATA; Schema: public; Owner: wunder
--

COPY public.games_categories (id, name) FROM stdin;
1	Other games
\.


--
-- Data for Name: platforms; Type: TABLE DATA; Schema: public; Owner: wunder
--

COPY public.platforms (id, name) FROM stdin;
s60	Symbian
\.


--
-- Data for Name: themes; Type: TABLE DATA; Schema: public; Owner: wunder
--

COPY public.themes (id, title, file, category, description, publisher, version, platform, screenshots_count, img, visible) FROM stdin;
\.


--
-- Data for Name: themes_categories; Type: TABLE DATA; Schema: public; Owner: wunder
--

COPY public.themes_categories (id, name) FROM stdin;
1	All
\.

--
-- Name: apps_categories_id_seq; Type: SEQUENCE SET; Schema: public; Owner: wunder
--

SELECT pg_catalog.setval('public.apps_categories_id_seq', 1, true);


--
-- Name: apps_id_seq; Type: SEQUENCE SET; Schema: public; Owner: wunder
--

SELECT pg_catalog.setval('public.apps_id_seq', 2, true);


--
-- Name: apps_rating_id_seq; Type: SEQUENCE SET; Schema: public; Owner: wunder
--

SELECT pg_catalog.setval('public.apps_rating_id_seq', 4, true);


--
-- Name: games_categories_id_seq; Type: SEQUENCE SET; Schema: public; Owner: wunder
--

SELECT pg_catalog.setval('public.games_categories_id_seq', 1, true);


--
-- Name: games_id_seq; Type: SEQUENCE SET; Schema: public; Owner: wunder
--

SELECT pg_catalog.setval('public.games_id_seq', 1, false);


--
-- Name: themes_categories_id_seq; Type: SEQUENCE SET; Schema: public; Owner: wunder
--

SELECT pg_catalog.setval('public.themes_categories_id_seq', 1, true);


--
-- Name: themes_id_seq; Type: SEQUENCE SET; Schema: public; Owner: wunder
--

SELECT pg_catalog.setval('public.themes_id_seq', 1, false);


--
-- Name: users_id_seq; Type: SEQUENCE SET; Schema: public; Owner: wunder
--

SELECT pg_catalog.setval('public.users_id_seq', 3, true);


--
-- Name: apps_categories apps_categories_pkey; Type: CONSTRAINT; Schema: public; Owner: wunder
--

ALTER TABLE ONLY public.apps_categories
    ADD CONSTRAINT apps_categories_pkey PRIMARY KEY (id);


--
-- Name: apps apps_pkey; Type: CONSTRAINT; Schema: public; Owner: wunder
--

ALTER TABLE ONLY public.apps
    ADD CONSTRAINT apps_pkey PRIMARY KEY (id);


--
-- Name: apps_rating apps_rating_pkey; Type: CONSTRAINT; Schema: public; Owner: wunder
--

ALTER TABLE ONLY public.apps_rating
    ADD CONSTRAINT apps_rating_pkey PRIMARY KEY (id);


--
-- Name: games_categories games_categories_pkey; Type: CONSTRAINT; Schema: public; Owner: wunder
--

ALTER TABLE ONLY public.games_categories
    ADD CONSTRAINT games_categories_pkey PRIMARY KEY (id);


--
-- Name: games games_pkey; Type: CONSTRAINT; Schema: public; Owner: wunder
--

ALTER TABLE ONLY public.games
    ADD CONSTRAINT games_pkey PRIMARY KEY (id);


--
-- Name: platforms platforms_pkey; Type: CONSTRAINT; Schema: public; Owner: wunder
--

ALTER TABLE ONLY public.platforms
    ADD CONSTRAINT platforms_pkey PRIMARY KEY (id);


--
-- Name: themes_categories themes_categories_pkey; Type: CONSTRAINT; Schema: public; Owner: wunder
--

ALTER TABLE ONLY public.themes_categories
    ADD CONSTRAINT themes_categories_pkey PRIMARY KEY (id);


--
-- Name: themes themes_pkey; Type: CONSTRAINT; Schema: public; Owner: wunder
--

ALTER TABLE ONLY public.themes
    ADD CONSTRAINT themes_pkey PRIMARY KEY (id);


--
-- Name: users users_pkey; Type: CONSTRAINT; Schema: public; Owner: wunder
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_pkey PRIMARY KEY (id);


--
-- Name: apps apps_category_fkey; Type: FK CONSTRAINT; Schema: public; Owner: wunder
--

ALTER TABLE ONLY public.apps
    ADD CONSTRAINT apps_category_fkey FOREIGN KEY (category) REFERENCES public.apps_categories(id);


--
-- Name: apps_rating apps_rating_content_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: wunder
--

ALTER TABLE ONLY public.apps_rating
    ADD CONSTRAINT apps_rating_content_id_fkey FOREIGN KEY (content_id) REFERENCES public.apps(id);


--
-- Name: apps_rating apps_rating_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: wunder
--

ALTER TABLE ONLY public.apps_rating
    ADD CONSTRAINT apps_rating_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id);


--
-- Name: games games_category_fkey; Type: FK CONSTRAINT; Schema: public; Owner: wunder
--

ALTER TABLE ONLY public.games
    ADD CONSTRAINT games_category_fkey FOREIGN KEY (category) REFERENCES public.games_categories(id);


--
-- Name: themes themes_category_fkey; Type: FK CONSTRAINT; Schema: public; Owner: wunder
--

ALTER TABLE ONLY public.themes
    ADD CONSTRAINT themes_category_fkey FOREIGN KEY (category) REFERENCES public.themes_categories(id);


--
-- PostgreSQL database dump complete
--

