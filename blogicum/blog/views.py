from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm
from django.core.paginator import Paginator
from django.db.models import Count
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from .forms import CommentForm, PostForm, ProfileForm
from .models import Category, Comment, Post


def published_posts():
    current_time = timezone.now()
    return Post.objects.filter(
        is_published=True,
        pub_date__lte=current_time,
        category__is_published=True,
    ).select_related('category', 'location', 'author').annotate(
        comment_count=Count('comments'),
    )


def paginate(request, queryset):
    return Paginator(queryset.order_by('-pub_date'), 10).get_page(
        request.GET.get('page'),
    )


def register(request):
    form = UserCreationForm(request.POST or None)
    if form.is_valid():
        user = form.save()
        login(request, user)
        return redirect('blog:index')
    return render(request, 'registration/registration_form.html', {'form': form})


@login_required
def profile_edit(request):
    form = ProfileForm(request.POST or None, instance=request.user)
    if form.is_valid():
        form.save()
        return redirect('blog:profile', username=request.user.username)
    return render(request, 'registration/profile_edit.html', {'form': form})


def index(request):
    page_obj = paginate(request, published_posts())
    return render(request, 'blog/index.html', {'page_obj': page_obj})


def post_detail(request, post_id):
    post = get_object_or_404(Post.objects.select_related('category', 'location', 'author'), pk=post_id)
    visible = (
        post.is_published and post.pub_date <= timezone.now()
        and post.category is not None and post.category.is_published
    )
    if not visible and not (request.user.is_authenticated and request.user == post.author):
        return get_object_or_404(published_posts(), pk=post_id)
    return render(request, 'blog/detail.html', {
        'post': post, 'form': CommentForm(), 'comments': post.comments.select_related('author'),
    })


def category_posts(request, category_slug):
    category = get_object_or_404(
        Category,
        slug=category_slug,
        is_published=True,
    )
    posts = paginate(request, published_posts().filter(category=category))
    return render(request, 'blog/category.html', {
        'category': category, 'page_obj': posts,
    })


def profile(request, username):
    from django.contrib.auth import get_user_model
    author = get_object_or_404(get_user_model(), username=username)
    posts = Post.objects.filter(author=author).select_related(
        'category', 'location',
    ).annotate(comment_count=Count('comments'))
    if request.user != author:
        posts = published_posts().filter(author=author)
    page_obj = paginate(request, posts)
    return render(request, 'blog/profile.html', {
        'profile': author, 'page_obj': page_obj,
    })


@login_required
def post_create(request):
    form = PostForm(request.POST or None, request.FILES or None)
    if form.is_valid():
        post = form.save(commit=False)
        post.author = request.user
        post.save()
        return redirect('blog:profile', username=request.user.username)
    return render(request, 'blog/create.html', {'form': form, 'is_edit': False})


@login_required
def post_edit(request, post_id):
    post = get_object_or_404(Post, pk=post_id)
    if post.author != request.user:
        return redirect('blog:post_detail', post_id=post.pk)
    form = PostForm(request.POST or None, request.FILES or None, instance=post)
    if form.is_valid():
        form.save()
        return redirect('blog:post_detail', post_id=post.pk)
    return render(request, 'blog/create.html', {'form': form, 'is_edit': True, 'post': post})


@login_required
def post_delete(request, post_id):
    post = get_object_or_404(Post, pk=post_id, author=request.user)
    if request.method == 'POST':
        post.delete()
        return redirect('blog:profile', username=request.user.username)
    return render(request, 'blog/create.html', {'form': PostForm(instance=post)})


@login_required
def comment_create(request, post_id):
    post = get_object_or_404(Post, pk=post_id)
    form = CommentForm(request.POST)
    if form.is_valid():
        comment = form.save(commit=False)
        comment.post, comment.author = post, request.user
        comment.save()
    return redirect('blog:post_detail', post_id=post_id)


@login_required
def comment_edit(request, post_id, comment_id):
    comment = get_object_or_404(Comment, pk=comment_id, post_id=post_id)
    if comment.author != request.user:
        return HttpResponseForbidden()
    form = CommentForm(request.POST or None, instance=comment)
    if form.is_valid():
        form.save()
        return redirect('blog:post_detail', post_id=post_id)
    return render(request, 'blog/comment.html', {'form': form, 'comment': comment})


@login_required
def comment_delete(request, post_id, comment_id):
    comment = get_object_or_404(Comment, pk=comment_id, post_id=post_id, author=request.user)
    if request.method == 'POST':
        comment.delete()
        return redirect('blog:post_detail', post_id=post_id)
    return render(request, 'blog/comment.html', {'comment': comment, 'is_delete': True})
